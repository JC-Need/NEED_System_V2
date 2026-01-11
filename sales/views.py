import json
import datetime
import openpyxl 
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

# Import Models
from .models import POSOrder, POSOrderItem, Quotation, QuotationItem
from inventory.models import Product, Category
from master_data.models import Customer
# from accounting.models import Income  <-- ❌ ปิดไว้ก่อนครับ เพราะยังไม่มีแอปบัญชี

# --- 1. หน้า Dashboard ---
@login_required
def sales_dashboard(request):
    return render(request, 'sales/dashboard.html')

# --- 2. POS System ---
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
            received_amount = data.get('received_amount', total_amount) # รับเงินมาเท่ายอดขาย (Default)

            # 1. สร้างหัวบิล
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
                status='PAID' # ✅ บังคับให้เป็น PAID ทันที เพื่อ Trigger คอมมิชชั่น!
            )

            # 2. วนลูปสินค้า -> บันทึก และ ตัดสต็อก
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
                # ตัดสต็อก
                product.stock_qty -= int(item['qty'])
                product.save()

            # 3. 💰 ลงบัญชี (ปิดไว้ก่อน รอทำระบบบัญชี)
            # Income.objects.create(...) 

            return JsonResponse({'success': True, 'order_code': order_code})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid Request'})

# --- 3. ระบบใบเสนอราคา (Quotation) ---

@login_required
def quotation_list(request):
    quotes = Quotation.objects.all().order_by('-id')
    return render(request, 'sales/quotation_list.html', {'quotes': quotes})

@csrf_exempt
@login_required
def quotation_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            items = data.get('items', [])

            # 1. สร้างหัวบิล
            now_str = datetime.datetime.now().strftime('%Y%m%d%H%M')
            code = f"QT-{now_str}"

            customer = Customer.objects.get(id=customer_id) if customer_id else None
            current_emp = getattr(request.user, 'employee', None)

            quotation = Quotation.objects.create(
                code=code,
                customer=customer,
                employee=current_emp,
                date=datetime.date.today(),
                status='DRAFT'
            )

            # 2. บันทึกรายการ
            total_val = 0
            for item in items:
                qty = int(item['qty'])
                price = float(item['price'])
                amount = qty * price
                total_val += amount

                product = Product.objects.get(id=item['id'])
                QuotationItem.objects.create(
                    quotation=quotation,
                    product=product,
                    description=product.name,
                    quantity=qty,
                    unit_price=price,
                    amount=amount
                )

            quotation.subtotal = total_val
            quotation.grand_total = total_val
            quotation.save()

            return JsonResponse({'success': True, 'code': code})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    customers = Customer.objects.all()
    products = Product.objects.filter(is_active=True)
    return render(request, 'sales/quotation_form.html', {
        'customers': customers,
        'products': products
    })

@login_required
def quotation_print(request, quote_id):
    quote = get_object_or_404(Quotation, id=quote_id)
    from master_data.models import CompanyInfo
    company = CompanyInfo.objects.first()
    context = {'quote': quote, 'company': company, 'items': quote.items.all()}
    return render(request, 'sales/quotation_print.html', context)

@login_required
def pos_print_slip(request, order_code):
    order = get_object_or_404(POSOrder, code=order_code)
    from master_data.models import CompanyInfo
    company = CompanyInfo.objects.first()
    context = {'order': order, 'items': order.items.all(), 'company': company}
    return render(request, 'sales/slip_print.html', context)

@login_required
def export_sales_excel(request):
    # ตรวจสอบว่ามี openpyxl หรือยัง (กันเหนียว)
    try:
        import openpyxl
    except ImportError:
        return HttpResponse("Server Error: openpyxl library not installed.", status=500)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    headers = ["วันที่/เวลา", "เลขที่บิล", "พนักงานขาย", "วิธีชำระ", "ยอดขาย (บาท)"]
    ws.append(headers)

    orders = POSOrder.objects.all().order_by('-created_at')
    total_sales = 0

    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d %H:%M')
        emp_name = order.employee.first_name if order.employee else "Admin/Unkown"
        ws.append([date_str, order.code, emp_name, order.payment_method, order.total_amount])
        total_sales += order.total_amount

    ws.append([])
    ws.append(["", "", "", "รวมทั้งสิ้น:", total_sales])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Sales_Report.xlsx"'
    wb.save(response)

    return response