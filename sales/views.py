import json
import datetime
import openpyxl
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.utils import timezone 

from .models import Quotation, QuotationItem, POSOrder, POSOrderItem
from inventory.models import Product, Category
from master_data.models import Customer, CompanyInfo
from hr.models import Employee
from .forms import QuotationForm

# ==========================================
# 1. หน้า Dashboard
# ==========================================
@login_required
def sales_dashboard(request):
    return render(request, 'sales/dashboard.html')

# ==========================================
# 2. ระบบ POS
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

            now_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            order_code = f"POS-{now_str}"
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
# 3. ใบเสนอราคา: หน้ารายการ (List)
# ==========================================
@login_required
def quotation_list(request):
    current_emp = getattr(request.user, 'employee', None)
    
    # ✅ เช็คสิทธิ์ Manager เพื่อส่งไปหน้า Template
    is_manager = False
    if request.user.is_superuser:
        is_manager = True
    elif current_emp:
        job_title = current_emp.position.title.lower() if current_emp.position else ""
        rank = current_emp.business_rank
        if ('manager' in job_title) or ('director' in job_title) or (rank in ['manager', 'director']):
            is_manager = True

    # --- Logic: การมองเห็นข้อมูล ---
    if is_manager: # ถ้าเป็น Manager (หรือ Superuser) เห็นทั้งหมด
        queryset = Quotation.objects.all()
    elif current_emp:
        # Sale เห็นของตัวเอง + ลูกน้อง
        subordinates = Employee.objects.none()
        try:
            found_subs = Employee.objects.filter(manager=current_emp)
            if found_subs.count() > 0: subordinates = found_subs
        except Exception: pass

        if subordinates.exists():
            team_ids = list(subordinates.values_list('id', flat=True))
            team_ids.append(current_emp.id)
            queryset = Quotation.objects.filter(employee_id__in=team_ids)
        else:
            queryset = Quotation.objects.filter(employee=current_emp)
    else:
        # กรณี User ทั่วไปที่ไม่ผูก Employee (และไม่ใช่ Superuser) -> เห็นทั้งหมด (Default)
        queryset = Quotation.objects.all()

    queryset = queryset.order_by('-created_at')

    # --- Search & Filter ---
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(code__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(employee__first_name__icontains=search_query)
        )

    date_start = request.GET.get('start_date')
    date_end = request.GET.get('end_date')
    if date_start: queryset = queryset.filter(date__gte=parse_date(date_start))
    if date_end: queryset = queryset.filter(date__lte=parse_date(date_end))

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sales/quotation_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'date_start': date_start,
        'date_end': date_end,
        'is_manager': is_manager, # ✅ ส่งค่านี้ไปบอกหน้าจอว่า "ฉันคือผู้จัดการนะ"
    })

# ==========================================
# 4. ใบเสนอราคา: สร้างใหม่ & แก้ไข
# ==========================================
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
            try:
                item_name = request.POST.get('item_name')
                qty = int(request.POST.get('quantity', 1))
                price_clean = request.POST.get('price', '0').replace(',', '')
                price = Decimal(price_clean)
                if item_name:
                    QuotationItem.objects.create(quotation=qt, item_name=item_name, quantity=qty, unit_price=price)
                    calculate_totals(qt)
                else: messages.error(request, "กรุณาระบุชื่อสินค้า")
            except Exception as e: messages.error(request, f"เกิดข้อผิดพลาด: {e}")
            return redirect('quotation_edit', qt_id=qt.id)

        elif 'update_info' in request.POST:
            qt.note = request.POST.get('note', '')
            discount_str = request.POST.get('discount', '').strip()
            qt.discount = Decimal(discount_str) if discount_str else Decimal(0)
            shipping_str = request.POST.get('shipping_cost', '').strip()
            qt.shipping_cost = Decimal(shipping_str) if shipping_str else Decimal(0)
            calculate_totals(qt)
            messages.success(request, "บันทึกข้อมูลเรียบร้อย")
            return redirect('quotation_edit', qt_id=qt.id)

    return render(request, 'sales/quotation_edit.html', {'qt': qt, 'products': products, 'item_total': item_total})

def calculate_totals(qt):
    item_sum = sum(item.quantity * item.unit_price for item in qt.items.all())
    shipping = qt.shipping_cost if qt.shipping_cost else Decimal(0)
    discount = qt.discount if qt.discount else Decimal(0)
    grand_total = (item_sum + shipping) - discount
    if grand_total < Decimal(0): grand_total = Decimal(0)
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

# ----------------------------------------------------
# ✅ ฟังก์ชันอนุมัติใบเสนอราคา (Approve Logic)
# ----------------------------------------------------
@login_required
def quotation_approve(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    
    current_emp = getattr(request.user, 'employee', None)
    is_manager = False
    
    if request.user.is_superuser:
        is_manager = True
    elif current_emp:
        job_title = current_emp.position.title.lower() if current_emp.position else ""
        rank = current_emp.business_rank
        if ('manager' in job_title) or ('director' in job_title) or (rank in ['manager', 'director']):
            is_manager = True

    if not is_manager:
        messages.error(request, "❌ คุณไม่มีสิทธิ์อนุมัติเอกสารนี้")
        return redirect('quotation_list')

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
    try: import openpyxl
    except ImportError: return HttpResponse("Server Error", status=500)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sales Report"
    ws.append(["วันที่/เวลา", "เลขที่บิล", "พนักงานขาย", "วิธีชำระ", "ยอดขาย (บาท)"])
    orders = POSOrder.objects.all().order_by('-created_at')
    total_sales = 0
    for order in orders:
        emp_name = order.employee.first_name if order.employee else "Admin"
        ws.append([order.created_at.strftime('%Y-%m-%d %H:%M'), order.code, emp_name, order.payment_method, order.total_amount])
        total_sales += order.total_amount
    ws.append([]); ws.append(["", "", "", "รวมทั้งสิ้น:", total_sales])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Sales_Report.xlsx"'
    wb.save(response)
    return response

@login_required
def api_search_customer(request):
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'results': []})
    customers = Customer.objects.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(phone__icontains=query)).values('id', 'code', 'name', 'tax_id', 'phone', 'address', 'sub_district', 'district', 'province', 'zip_code')[:10]
    results = []
    for c in customers:
        addr_parts = [c['address'], c['sub_district'], c['district'], c['province'], c['zip_code']]
        full_address = " ".join([p for p in addr_parts if p])
        results.append({'id': c['id'], 'code': c['code'], 'name': c['name'], 'tax_id': c['tax_id'] or '', 'phone': c['phone'] or '', 'address': full_address})
    return JsonResponse({'results': results})