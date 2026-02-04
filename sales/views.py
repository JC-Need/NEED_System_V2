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

# ==========================================
# 🔧 Utility & Helper
# ==========================================
def get_next_document_number():
    now = timezone.now()
    prefix = f"DLN-{now.strftime('%y%m')}"
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
    return f"{prefix}-{new_seq:04d}"

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

# ==========================================
# 1. หน้า Dashboard
# ==========================================
@login_required
def sales_dashboard(request):
    today = timezone.now().date()
    target_employees, scope_title = get_target_employees(request.user)

    # 1. คำนวณยอดรวม (เงิน)
    pos_today = POSOrder.objects.filter(created_at__date=today, status='PAID', employee__in=target_employees).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    inv_today = Invoice.objects.filter(date=today, status='PAID', employee__in=target_employees).aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_sales_today = pos_today + inv_today

    # 2. นับจำนวนบิล (POS + Invoice)
    count_pos = POSOrder.objects.filter(created_at__date=today, employee__in=target_employees).count()
    count_inv = Invoice.objects.filter(date=today, employee__in=target_employees).count()
    total_orders = count_pos + count_inv

    # 3. งานค้าง
    pending_approval_quotes = Quotation.objects.filter(status='DRAFT', employee__in=target_employees).count()
    pending_closing_quotes = Quotation.objects.filter(status='APPROVED', employee__in=target_employees).count()

    # 4. Top Seller
    current_month = today.month
    top_seller = POSOrder.objects.filter(created_at__month=current_month, employee__in=target_employees)\
        .values('employee__first_name', 'employee__photo')\
        .annotate(total=Sum('total_amount'))\
        .order_by('-total').first()

    # 5. รายการขายล่าสุด (รวม POS และ Invoice)
    recent_pos = list(POSOrder.objects.filter(employee__in=target_employees).order_by('-created_at')[:10])
    recent_inv = list(Invoice.objects.filter(employee__in=target_employees).order_by('-created_at')[:10])
    
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

# ==========================================
# 2. Sales Hub & Convert
# ==========================================
@login_required
def sales_hub(request):
    current_emp = getattr(request.user, 'employee', None)
    target_employees, _ = get_target_employees(request.user)
    
    qs = Quotation.objects.filter(status='APPROVED', employee__in=target_employees)
    ready_quotes = qs.order_by('-created_at')
    
    today = timezone.now().date()
    inv_qs = Invoice.objects.filter(date=today, employee__in=target_employees)
    pos_qs = POSOrder.objects.filter(created_at__date=today, employee__in=target_employees)

    return render(request, 'sales/sales_hub.html', {
        'ready_quotes': ready_quotes,
        'today_invoices': inv_qs.order_by('-created_at'),
        'today_pos': pos_qs.order_by('-created_at')
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
        status='UNPAID'
    )
    qt.status = 'CONVERTED'
    qt.save()
    messages.success(request, f"✅ เปิดใบขายสินค้า {new_code} เรียบร้อยแล้ว")
    return redirect('invoice_list')

# ==========================================
# 3. ระบบ POS
# ==========================================
@login_required
def pos_home(request):
    products = Product.objects.filter(is_active=True, stock_qty__gt=0)
    categories = Category.objects.all()
    return render(request, 'sales/pos_home.html', {'products': products, 'categories': categories})

@csrf_exempt
@login_required
def pos_checkout(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart = data.get('cart', [])
            total_amount = data.get('total_amount', 0)
            received_amount = data.get('received_amount', total_amount)
            order_code = get_next_document_number()
            current_emp = getattr(request.user, 'employee', None)

            order = POSOrder.objects.create(
                code=order_code,
                employee=current_emp,
                total_amount=total_amount,
                received_amount=received_amount,
                change_amount=float(received_amount) - float(total_amount),
                payment_method='CASH',
                status='PAID'
            )
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
    context = {'order': order, 'items': order.items.all(), 'company': company}
    return render(request, 'sales/slip_print.html', context)

# ==========================================
# 4. ระบบใบเสนอราคา
# ==========================================
@login_required
def quotation_list(request):
    target_employees, _ = get_target_employees(request.user)
    queryset = Quotation.objects.filter(employee__in=target_employees).order_by('-created_at')

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
        'is_manager': is_manager
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
            prefix = f"QT-{now.strftime('%y%m')}"
            last = Quotation.objects.filter(code__startswith=prefix).order_by('code').last()
            seq = int(last.code.split('-')[-1]) + 1 if last else 1
            qt.code = f"{prefix}-{seq:03d}"
            qt.save()
            messages.success(request, f"สร้างใบเสนอราคา {qt.code} เรียบร้อย")
            return redirect('quotation_edit', qt_id=qt.id)
    else:
        form = QuotationForm(initial={'date': datetime.date.today(), 'valid_until': datetime.date.today() + datetime.timedelta(days=15)})
    return render(request, 'sales/quotation_form.html', {'form': form})

@login_required
def quotation_edit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    products = Product.objects.filter(is_active=True)
    item_total = sum(i.quantity * i.unit_price for i in qt.items.all())
    if request.method == 'POST':
        if 'add_item' in request.POST:
            item_name = request.POST.get('item_name')
            qty = int(request.POST.get('quantity', 1))
            price = Decimal(request.POST.get('price', '0').replace(',', ''))
            if item_name:
                QuotationItem.objects.create(quotation=qt, item_name=item_name, quantity=qty, unit_price=price)
                calculate_totals(qt)
            return redirect('quotation_edit', qt_id=qt.id)
        elif 'update_info' in request.POST:
            qt.note = request.POST.get('note', '')
            qt.discount = Decimal(request.POST.get('discount', '0') or 0)
            qt.shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or 0)
            calculate_totals(qt)
            messages.success(request, "บันทึกข้อมูลเรียบร้อย")
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
def quotation_print(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    company = CompanyInfo.objects.first()
    item_total = sum(item.quantity * item.unit_price for item in qt.items.all())
    return render(request, 'sales/quotation_print.html', {'qt': qt, 'company': company, 'item_total': item_total})

@login_required
def export_sales_excel(request):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sales Report"
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
    customers = Customer.objects.filter(Q(name__icontains=query) | Q(code__icontains=query))[:10]
    results = []
    for c in customers:
        addr_parts = [
            c.address,
            f"ต.{c.sub_district}" if c.sub_district else "",
            f"อ.{c.district}" if c.district else "",
            f"จ.{c.province}" if c.province else "",
            c.zip_code
        ]
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

# ==========================================
# 5. ระบบใบรับชำระเงิน (Invoice + POS) ★ แก้ไขใหม่
# ==========================================
@login_required
def invoice_list(request):
    target_employees, _ = get_target_employees(request.user)
    
    # 1. เตรียม Queryset ทั้ง 2 แบบ
    qs_invoice = Invoice.objects.filter(employee__in=target_employees)
    qs_pos = POSOrder.objects.filter(employee__in=target_employees)

    # 2. กรองข้อมูล (Search)
    search_query = request.GET.get('q', '')
    if search_query:
        qs_invoice = qs_invoice.filter(Q(code__icontains=search_query) | Q(customer__name__icontains=search_query))
        qs_pos = qs_pos.filter(code__icontains=search_query) # POS ไม่มี Customer

    # 3. กรองวันที่
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        qs_invoice = qs_invoice.filter(date__gte=start_date)
        qs_pos = qs_pos.filter(created_at__date__gte=start_date)
    if end_date:
        qs_invoice = qs_invoice.filter(date__lte=end_date)
        qs_pos = qs_pos.filter(created_at__date__lte=end_date)

    # 4. แปลงเป็น List และรวมกัน
    list_invoice = list(qs_invoice)
    list_pos = list(qs_pos)
    
    # รวมและเรียงลำดับ (ใหม่สุดขึ้นก่อน)
    combined_list = sorted(list_invoice + list_pos, key=lambda x: x.created_at, reverse=True)

    # 5. แบ่งหน้า (Pagination)
    paginator = Paginator(combined_list, 15) # แสดง 15 รายการต่อหน้า
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sales/invoice_list.html', {
        'page_obj': page_obj, 
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date
    })

@login_required
def invoice_print(request, inv_id):
    inv = get_object_or_404(Invoice, pk=inv_id)
    company = CompanyInfo.objects.first()
    
    # ดึงรายการสินค้า (มาจาก Quotation หรือ POS)
    items = []
    if inv.quotation_ref:
        items = inv.quotation_ref.items.all()
    
    return render(request, 'sales/invoice_print.html', {
        'inv': inv, 
        'company': company, 
        'items': items
    })