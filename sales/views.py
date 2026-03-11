import json
import datetime
import openpyxl
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count, Max
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.utils import timezone 

from .models import Quotation, QuotationItem, POSOrder, POSOrderItem, Invoice
from inventory.models import Product, Category
from master_data.models import Customer, CompanyInfo
from hr.models import Employee
from .forms import QuotationForm

def get_next_document_number():
    now = timezone.now()
    thai_year = (now.year + 543) % 100
    prefix = f"DLN-{thai_year:02d}{now.strftime('%m')}"
    
    last_inv = Invoice.objects.filter(code__startswith=prefix).aggregate(Max('code'))['code__max']
    last_pos = POSOrder.objects.filter(code__startswith=prefix).aggregate(Max('code'))['code__max']
    
    max_seq = 0
    if last_inv:
        try: max_seq = max(max_seq, int(last_inv.split('-')[-1]))
        except: pass
    if last_pos:
        try: max_seq = max(max_seq, int(last_pos.split('-')[-1]))
        except: pass
        
    new_seq = max_seq + 1
    return f"{prefix}-{new_seq:03d}"

def get_target_employees(user):
    current_emp = getattr(user, 'employee', None)
    if user.is_superuser:
        return Employee.objects.all(), "Admin View"
    elif current_emp:
        rank = current_emp.business_rank.lower()
        job_title = current_emp.position.title.lower() if current_emp.position else ""
        if rank in ['manager', 'director'] or 'manager' in job_title:
            return Employee.objects.all(), "Manager View"
        elif rank == 'supervisor':
            if current_emp.department:
                return Employee.objects.filter(department=current_emp.department), f"Team {current_emp.department.name}"
            else:
                return Employee.objects.filter(Q(id=current_emp.id) | Q(introducer=current_emp)), "Direct Team"
        else:
            return Employee.objects.filter(id=current_emp.id), "Self View"
    else:
        return Employee.objects.none(), "-"

def get_sales_queryset(model_class, user, target_employees):
    if user.is_superuser:
        return model_class.objects.all()
    else:
        return model_class.objects.filter(employee__in=target_employees)

def is_sales_authorized(user):
    if user.is_superuser: 
        return True
    
    user_groups = list(user.groups.values_list('name', flat=True))
    if 'Sales' in user_groups:
        return True
        
    if hasattr(user, 'employee') and user.employee:
        dept = user.employee.department.name if user.employee.department else ''
        rank = user.employee.business_rank if user.employee.business_rank else ''
        
        if 'ขาย' in dept or 'Sales' in dept:
            return True
        if ('บัญชี' in dept or 'Accounting' in dept) and rank in ['Manager', 'Executive', 'Director', 'ผู้จัดการ']:
            return True
            
    return False

@login_required
def sales_dashboard(request):
    if not is_sales_authorized(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เข้าถึงภาพรวมฝ่ายขาย")
        return redirect('dashboard')

    today = timezone.now().date()
    target_employees, scope_title = get_target_employees(request.user)

    pos_qs = get_sales_queryset(POSOrder, request.user, target_employees)
    inv_qs = get_sales_queryset(Invoice, request.user, target_employees)
    qt_qs = get_sales_queryset(Quotation, request.user, target_employees)

    pos_today = pos_qs.filter(created_at__date=today, status='PAID').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    inv_today = inv_qs.filter(date=today, status='PAID').aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_sales_today = pos_today + inv_today

    count_pos = pos_qs.filter(created_at__date=today).count()
    count_inv = inv_qs.filter(date=today).count()
    total_orders = count_pos + count_inv

    pending_approval_quotes = qt_qs.filter(status='DRAFT').count()
    pending_closing_quotes = qt_qs.filter(status='APPROVED').count()

    current_month = today.month
    top_seller = POSOrder.objects.filter(created_at__month=current_month, employee__in=target_employees)\
        .values('employee__first_name', 'employee__photo')\
        .annotate(total=Sum('total_amount'))\
        .order_by('-total').first()

    recent_pos = list(pos_qs.order_by('-created_at')[:10])
    recent_inv = list(inv_qs.order_by('-created_at')[:10])
    combined_sales = sorted(recent_pos + recent_inv, key=lambda x: x.created_at, reverse=True)[:10]

    context = {
        'total_sales_today': total_sales_today,
        'total_orders': total_orders,
        'pending_approval_quotes': pending_approval_quotes,
        'pending_closing_quotes': pending_closing_quotes,
        'top_seller': top_seller,
        'recent_sales': combined_sales, 
        'scope_title': scope_title,
    }
    return render(request, 'sales/dashboard.html', context)

@login_required
def sales_hub(request):
    if not is_sales_authorized(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เปิดบิลขาย")
        return redirect('dashboard')

    target_employees, _ = get_target_employees(request.user)
    qt_qs = get_sales_queryset(Quotation, request.user, target_employees)
    inv_qs = get_sales_queryset(Invoice, request.user, target_employees)
    pos_qs = get_sales_queryset(POSOrder, request.user, target_employees)

    ready_quotes = qt_qs.filter(status='APPROVED').order_by('-created_at')
    today = timezone.now().date()
    today_invoices = inv_qs.filter(date=today).order_by('-created_at')
    today_pos = pos_qs.filter(created_at__date=today).order_by('-created_at')

    return render(request, 'sales/sales_hub.html', {
        'ready_quotes': ready_quotes,
        'today_invoices': today_invoices,
        'today_pos': today_pos
    })

@login_required
def convert_quote_to_invoice(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    new_code = get_next_document_number()
    
    invoice = Invoice.objects.create(
        code=new_code,
        quotation_ref=qt,
        date=timezone.now().date(),
        customer=qt.customer,
        employee=request.user.employee if hasattr(request.user, 'employee') else None,
        grand_total=qt.grand_total,
        status='PENDING'
    )
    qt.status = 'CONVERTED'
    qt.save()
    messages.success(request, f"✅ เปิดใบขายสินค้า {new_code} เรียบร้อย (รอตรวจสอบยอดเงิน)")
    return redirect('invoice_list')

@login_required
def pos_home(request):
    if not is_sales_authorized(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบ POS")
        return redirect('dashboard')

    # 🌟 แก้ไข: เพิ่มฟิลเตอร์ product_type='FG' เพื่อดึงเฉพาะสินค้าสำเร็จรูป 🌟
    products = Product.objects.filter(is_active=True, stock_qty__gt=0, product_type='FG')
    categories = Category.objects.all()
    return render(request, 'sales/pos_home.html', {'products': products, 'categories': categories})

@csrf_exempt
@login_required
def pos_checkout(request):
    if request.method == 'POST':
        try:
            payment_method = request.POST.get('payment_method', 'CASH')
            total_amount = Decimal(request.POST.get('total_amount', 0))
            received_amount = Decimal(request.POST.get('received_amount', 0))
            
            cust_id = request.POST.get('customer_id')
            cust_name = request.POST.get('customer_name', '')
            cust_addr = request.POST.get('customer_address', '')
            cust_phone = request.POST.get('customer_phone', '')
            cust_tax = request.POST.get('customer_tax_id', '')

            cart_json = request.POST.get('cart', '[]')
            cart = json.loads(cart_json)

            order_code = get_next_document_number()
            current_emp = getattr(request.user, 'employee', None)

            customer_obj = None
            if cust_id:
                try: customer_obj = Customer.objects.get(id=cust_id)
                except: pass

            order = POSOrder.objects.create(
                code=order_code,
                employee=current_emp,
                total_amount=total_amount,
                received_amount=received_amount,
                change_amount=received_amount - total_amount,
                payment_method=payment_method,
                status='PENDING', 
                customer=customer_obj, 
                customer_name=cust_name,
                customer_address=cust_addr,
                customer_phone=cust_phone,
                customer_tax_id=cust_tax
            )

            if payment_method == 'TRANSFER':
                if 'transfer_slip' in request.FILES:
                    order.transfer_slip = request.FILES['transfer_slip']
            elif payment_method == 'CHECK':
                order.check_number = request.POST.get('check_number', '')
                order.check_bank = request.POST.get('check_bank', '')
            
            order.save()

            for item in cart:
                product = Product.objects.get(id=item['id'])
                POSOrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    quantity=item['qty'],
                    price=item['price'],
                    total_price=float(item['qty']) * float(item['price'])
                )
                product.stock_qty -= int(item['qty'])
                product.save()

            return JsonResponse({'success': True, 'order_code': order_code})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid Request'})

@login_required
def pos_print_slip(request, order_code):
    order = get_object_or_404(POSOrder, code=order_code)
    company = CompanyInfo.objects.first()
    
    items = list(order.items.all())
    for item in items:
        item.item_name = item.product_name  
        item.unit_price = item.price        
        item.amount = item.total_price      
        
    payment_note = "ชำระโดย: เงินสด (Cash)"
    if order.payment_method == 'TRANSFER':
        payment_note = "ชำระโดย: โอนเงิน (Bank Transfer)"
    elif order.payment_method == 'CHECK':
        payment_note = f"ชำระโดย: เช็คธนาคาร {order.check_bank} #{order.check_number}"

    context = {
        'inv': order,
        'company': company,
        'items': items,
        'subtotal': order.total_amount,
        'tax_amount': 0,
        'discount': 0,
        'shipping_cost': 0,
        'note': payment_note,
        'is_pos': True 
    }
    return render(request, 'sales/invoice_print.html', context)

@login_required
def quotation_list(request):
    target_employees, _ = get_target_employees(request.user)
    queryset = get_sales_queryset(Quotation, request.user, target_employees).order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(Q(code__icontains=search_query) | Q(customer_name__icontains=search_query))

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    is_manager = False
    current_emp = getattr(request.user, 'employee', None)
    if request.user.is_superuser: is_manager = True
    elif current_emp:
        rank = current_emp.business_rank.lower()
        if rank in ['manager', 'director'] or 'manager' in current_emp.position.title.lower():
            is_manager = True
            
    return render(request, 'sales/quotation_list.html', {
        'page_obj': page_obj, 
        'search_query': search_query, 
        'is_manager': is_manager,
        'status_filter': status_filter
    })

@login_required
def quotation_create(request):
    if request.method == 'POST':
        form = QuotationForm(request.POST)
        if form.is_valid():
            qt = form.save(commit=False)
            qt.created_by = request.user 
            if hasattr(request.user, 'employee'): qt.employee = request.user.employee
            cust_id = request.POST.get('customer_id')
            if cust_id:
                try: qt.customer = Customer.objects.get(pk=cust_id)
                except Customer.DoesNotExist: pass
            now = datetime.datetime.now()
            thai_year = (now.year + 543) % 100
            prefix = f"QT-{thai_year:02d}{now.strftime('%m')}"
            last = Quotation.objects.filter(code__startswith=prefix).order_by('code').last()
            seq = int(last.code.split('-')[-1]) + 1 if last else 1
            qt.code = f"{prefix}-{seq:03d}"
            qt.save()
            messages.success(request, f"ร่างใบเสนอราคา {qt.code} เรียบร้อย กรุณาเพิ่มรายการสินค้า")
            return redirect('quotation_edit', qt_id=qt.id)
    else:
        form = QuotationForm(initial={'date': datetime.date.today(), 'valid_until': datetime.date.today() + datetime.timedelta(days=15)})
    return render(request, 'sales/quotation_form.html', {'form': form})

@login_required
def quotation_edit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    # 🌟 แก้ไข: หน้าใบเสนอราคาก็ควรดึงเฉพาะสินค้าสำเร็จรูป (FG) มาขายเหมือนกันค่ะ 🌟
    products = Product.objects.filter(is_active=True, product_type='FG')
    item_total = sum(i.quantity * i.unit_price for i in qt.items.all())
    
    if request.method == 'POST':
        if qt.status in ['CONVERTED', 'CANCELLED']:
            messages.error(request, "❌ ไม่สามารถแก้ไขได้ เนื่องจากใบเสนอราคานี้ถูกล็อกหรือยกเลิกไปแล้ว")
            return redirect('quotation_edit', qt_id=qt.id)

        if 'add_item' in request.POST:
            item_name = request.POST.get('item_name')
            qty = int(request.POST.get('quantity', 1))
            price = Decimal(request.POST.get('price', '0').replace(',', ''))
            if item_name:
                QuotationItem.objects.create(quotation=qt, item_name=item_name, quantity=qty, unit_price=price)
                calculate_totals(qt)
            return redirect('quotation_edit', qt_id=qt.id)
            
        elif 'update_info' in request.POST or 'finish_quote' in request.POST:
            qt.note = request.POST.get('note', '')
            qt.discount = Decimal(request.POST.get('discount', '0') or 0)
            qt.shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or 0)
            calculate_totals(qt)
            
            if 'finish_quote' in request.POST:
                messages.success(request, f"✅ สร้างใบเสนอราคา {qt.code} เสร็จสมบูรณ์แล้ว! (รอผู้จัดการอนุมัติ)")
                return redirect('quotation_list')
            else:
                messages.success(request, "อัปเดตยอดเงินและหมายเหตุเรียบร้อย")
                return redirect('quotation_edit', qt_id=qt.id)
                
    return render(request, 'sales/quotation_edit.html', {'qt': qt, 'products': products, 'item_total': item_total})

def calculate_totals(qt):
    item_sum = sum(item.quantity * item.unit_price for item in qt.items.all())
    shipping = qt.shipping_cost if qt.shipping_cost else Decimal(0)
    discount = qt.discount if qt.discount else Decimal(0)
    grand_total = (item_sum + shipping) - discount
    if grand_total < 0: grand_total = 0
    qt.subtotal = grand_total / Decimal('1.07')
    qt.tax_amount = grand_total - qt.subtotal
    qt.grand_total = grand_total
    qt.save()

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(QuotationItem, pk=item_id)
    qt = item.quotation
    
    if qt.status in ['CONVERTED', 'CANCELLED']:
        messages.error(request, "❌ ไม่สามารถลบรายการได้ เนื่องจากใบเสนอราคานี้ถูกล็อกหรือยกเลิกไปแล้ว")
        return redirect('quotation_edit', qt_id=qt.id)
        
    item.delete()
    calculate_totals(qt)
    return redirect('quotation_edit', qt_id=qt.id)

@login_required
def quotation_approve(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    current_emp = getattr(request.user, 'employee', None)
    qt.status = 'APPROVED'
    qt.approved_by = current_emp
    qt.approved_at = timezone.now()
    qt.save()
    messages.success(request, f"✅ อนุมัติใบเสนอราคา {qt.code} เรียบร้อยแล้ว")
    return redirect('quotation_list')

@login_required
def quotation_cancel(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    
    current_emp = getattr(request.user, 'employee', None)
    is_manager = request.user.is_superuser or request.user.groups.filter(name__icontains='Manager').exists()
    is_owner = (qt.employee == current_emp) if current_emp else False
    
    if is_manager or is_owner:
        if qt.status in ['DRAFT', 'APPROVED']:
            qt.status = 'CANCELLED'
            qt.save()
            messages.warning(request, f"⚠️ ยกเลิกใบเสนอราคา {qt.code} เรียบร้อยแล้ว (เอกสารนี้ถือเป็นโมฆะ)")
        else:
            messages.error(request, "❌ ไม่สามารถยกเลิกได้ เนื่องจากเอกสารถูกนำไปเปิดบิลแล้ว")
    else:
        messages.error(request, "❌ คุณไม่มีสิทธิ์ยกเลิกใบเสนอราคานี้")
        
    return redirect('quotation_list')

@login_required
def quotation_print(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    company = CompanyInfo.objects.first()
    item_total = sum(item.quantity * item.unit_price for item in qt.items.all())
    return render(request, 'sales/quotation_print.html', {'qt': qt, 'company': company, 'item_total': item_total})

@login_required
def export_sales_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Sales Report"
    ws.append(["วันที่", "เลขที่เอกสาร", "ประเภท", "ยอดขาย"])
    for p in POSOrder.objects.all():
        ws.append([p.created_at.strftime('%Y-%m-%d'), p.code, "POS", p.total_amount])
    for i in Invoice.objects.all():
        ws.append([i.date.strftime('%Y-%m-%d'), i.code, "Invoice", i.grand_total])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Sales_Report.xlsx"'
    wb.save(response)
    return response

@login_required
def api_search_customer(request):
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'results': []})
    customers = Customer.objects.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(phone__icontains=query))[:10]
    results = []
    for c in customers:
        addr_parts = [c.address, f"ต.{c.sub_district}" if c.sub_district else "", f"อ.{c.district}" if c.district else "", f"จ.{c.province}" if c.province else "", c.zip_code]
        full_address = " ".join(filter(None, addr_parts))
        results.append({
            'id': c.id, 
            'name': c.name, 
            'code': c.code, 
            'address': full_address, 
            'tax_id': c.tax_id, 
            'phone': c.phone
        })
    return JsonResponse({'results': results})

@csrf_exempt
@login_required
def api_create_customer(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            code = request.POST.get('code')
            phone = request.POST.get('phone')
            tax_id = request.POST.get('tax_id')
            address = request.POST.get('address')
            
            if not code:
                count = Customer.objects.count() + 1
                code = f"C{count:04d}"

            customer = Customer.objects.create(
                name=name,
                code=code,
                phone=phone,
                tax_id=tax_id,
                address=address
            )
            return JsonResponse({
                'success': True,
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'address': customer.address,
                    'tax_id': customer.tax_id,
                    'phone': customer.phone
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid Method'})

@login_required
def invoice_list(request):
    target_employees, _ = get_target_employees(request.user)
    qs_invoice = get_sales_queryset(Invoice, request.user, target_employees)
    qs_pos = get_sales_queryset(POSOrder, request.user, target_employees)

    search_query = request.GET.get('q', '')
    if search_query:
        qs_invoice = qs_invoice.filter(Q(code__icontains=search_query) | Q(customer__name__icontains=search_query))
        qs_pos = qs_pos.filter(code__icontains=search_query)

    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'PENDING':
            qs_invoice = qs_invoice.filter(Q(status='PENDING') | Q(status='UNPAID'))
            qs_pos = qs_pos.filter(Q(status='PENDING') | Q(status='UNPAID'))
        else:
            qs_invoice = qs_invoice.filter(status=status_filter)
            qs_pos = qs_pos.filter(status=status_filter)

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and start_date != 'None':
        qs_invoice = qs_invoice.filter(date__gte=start_date)
        qs_pos = qs_pos.filter(created_at__date__gte=start_date)
    
    if end_date and end_date != 'None':
        qs_invoice = qs_invoice.filter(date__lte=end_date)
        qs_pos = qs_pos.filter(created_at__date__lte=end_date)

    combined_list = sorted(list(qs_invoice) + list(qs_pos), key=lambda x: x.created_at, reverse=True)
    paginator = Paginator(combined_list, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/invoice_list.html', {
        'page_obj': page_obj, 
        'search_query': search_query, 
        'start_date': start_date, 
        'end_date': end_date,
        'status_filter': status_filter
    })

@login_required
def confirm_payment(request, doc_type, doc_id):
    if doc_type == 'pos':
        obj = get_object_or_404(POSOrder, id=doc_id)
    else:
        obj = get_object_or_404(Invoice, id=doc_id)
        
    obj.status = 'PAID'
    obj.save()
    
    messages.success(request, f"✅ ยืนยันการชำระเงินเอกสาร {obj.code} เรียบร้อยแล้ว")
    return redirect('invoice_list')

@login_required
def invoice_print(request, inv_id):
    inv = get_object_or_404(Invoice, pk=inv_id)
    company = CompanyInfo.objects.first()
    
    items = []
    subtotal = 0
    tax_amount = 0
    discount = 0
    shipping_cost = 0
    note = ""

    if inv.quotation_ref:
        qt = inv.quotation_ref
        items = list(qt.items.all()) 
        for item in items:
            item.amount = item.quantity * item.unit_price 
        subtotal = qt.subtotal
        tax_amount = qt.tax_amount
        discount = qt.discount
        shipping_cost = qt.shipping_cost
        note = qt.note
        
        if not getattr(inv, 'customer_name', None):
            inv.customer_name = qt.customer_name
            inv.customer_address = qt.customer_address
            inv.customer_tax_id = qt.customer_tax_id
            inv.customer_phone = qt.customer_phone
    
    if not hasattr(inv, 'total_amount'):
        inv.total_amount = inv.grand_total

    context = {
        'inv': inv,
        'company': company,
        'items': items,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'discount': discount,
        'shipping_cost': shipping_cost,
        'note': note,
    }
    return render(request, 'sales/invoice_print.html', context)