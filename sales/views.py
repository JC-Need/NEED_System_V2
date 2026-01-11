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

# Import Models
from .models import Quotation, QuotationItem, POSOrder, POSOrderItem
from inventory.models import Product, Category
from master_data.models import Customer, CompanyInfo
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
    queryset = Quotation.objects.all().order_by('-created_at')
    
    search_query = request.GET.get('q')
    if search_query:
        queryset = queryset.filter(
            Q(code__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sales/quotation_list.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })

# ==========================================
# 4. ใบเสนอราคา: สร้างใหม่ Step 1
# ==========================================
@login_required
def quotation_create(request):
    if request.method == 'POST':
        form = QuotationForm(request.POST)
        if form.is_valid():
            qt = form.save(commit=False)
            qt.created_by = request.user
            
            now = datetime.datetime.now()
            prefix = f"QT-{now.strftime('%y%m')}"
            last = Quotation.objects.filter(code__startswith=prefix).order_by('code').last()
            
            if last:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except:
                    seq = 1
            else:
                seq = 1
            
            qt.code = f"{prefix}-{seq:03d}"
            qt.save()
            
            # แจ้งเตือนแค่ครั้งแรก (สร้างสำเร็จ)
            messages.success(request, f"สร้างใบเสนอราคา {qt.code} เรียบร้อย")
            return redirect('quotation_edit', qt_id=qt.id)
    else:
        form = QuotationForm(initial={
            'date': datetime.date.today(),
            'valid_until': datetime.date.today() + datetime.timedelta(days=15)
        })

    customers = Customer.objects.filter(is_active=True)
    return render(request, 'sales/quotation_form.html', {'form': form, 'customers': customers})

# ==========================================
# 5. ใบเสนอราคา: แก้ไข Step 2
# ==========================================
@login_required
def quotation_edit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    products = Product.objects.filter(is_active=True)
    customers = Customer.objects.filter(is_active=True)
    
    item_total = sum(i.quantity * i.unit_price for i in qt.items.all())

    if request.method == 'POST':
        # --- กรณี 1: เพิ่มสินค้า (❌ ไม่มีข้อความ) ---
        if 'add_item' in request.POST:
            try:
                item_name = request.POST.get('item_name')
                qty = int(request.POST.get('quantity', 1))
                price = Decimal(request.POST.get('price', 0))

                if item_name:
                    QuotationItem.objects.create(
                        quotation=qt,
                        item_name=item_name,
                        quantity=qty,
                        unit_price=price
                    )
                    calculate_totals(qt)
                    # ✅ เพิ่มเสร็จแล้วเงียบ (Silent Add)
                else:
                    messages.error(request, "กรุณาระบุชื่อสินค้า")
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาด: {e}")
            
            return redirect('quotation_edit', qt_id=qt.id)

        # --- กรณี 2: บันทึกยอด (✅ มีข้อความ) ---
        elif 'update_info' in request.POST:
            qt.note = request.POST.get('note', '')
            qt.discount = Decimal(request.POST.get('discount', 0))
            qt.shipping_cost = Decimal(request.POST.get('shipping_cost', 0))
            calculate_totals(qt)
            
            # ✅ โชว์ข้อความนี้อันเดียวครับ!
            messages.success(request, "บันทึกข้อมูลเรียบร้อย")
            return redirect('quotation_edit', qt_id=qt.id)

    return render(request, 'sales/quotation_edit.html', {
        'qt': qt,
        'products': products,
        'item_total': item_total
    })

# ==========================================
# 6. ฟังก์ชันคำนวณ & ลบสินค้า
# ==========================================
def calculate_totals(qt):
    item_sum = sum(item.quantity * item.unit_price for item in qt.items.all())
    shipping = qt.shipping_cost if qt.shipping_cost else Decimal(0)
    discount = qt.discount if qt.discount else Decimal(0)

    grand_total = (item_sum + shipping) - discount
    if grand_total < Decimal(0): grand_total = Decimal(0)

    qt.subtotal = grand_total / Decimal('1.07')
    qt.vat_amount = grand_total - qt.subtotal
    qt.grand_total = grand_total
    qt.save()

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(QuotationItem, pk=item_id)
    qt = item.quotation
    item.delete()
    calculate_totals(qt)
    # ✅ ลบเสร็จแล้วเงียบ (Silent Delete)
    return redirect('quotation_edit', qt_id=qt.id)

@login_required
def quotation_print(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    company = CompanyInfo.objects.first()
    return render(request, 'sales/quotation_print.html', {'qt': qt, 'company': company})

@login_required
def export_sales_excel(request):
    try:
        import openpyxl
    except ImportError:
        return HttpResponse("Server Error: openpyxl library not installed.", status=500)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    ws.append(["วันที่/เวลา", "เลขที่บิล", "พนักงานขาย", "วิธีชำระ", "ยอดขาย (บาท)"])

    orders = POSOrder.objects.all().order_by('-created_at')
    total_sales = 0
    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d %H:%M')
        emp_name = order.employee.first_name if order.employee else "Admin"
        ws.append([date_str, order.code, emp_name, order.payment_method, order.total_amount])
        total_sales += order.total_amount

    ws.append([])
    ws.append(["", "", "", "รวมทั้งสิ้น:", total_sales])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Sales_Report.xlsx"'
    wb.save(response)
    return response