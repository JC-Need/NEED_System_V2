import json
import datetime
import openpyxl # ✅ เพิ่มตัวนี้
from django.http import HttpResponse # ✅ เพิ่มตัวนี้
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

# Import Models
from .models import POSOrder, POSOrderItem, Quotation, QuotationItem
from inventory.models import Product, Category
from master_data.models import Customer
from accounting.models import Income

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

            # 1. สร้างหัวบิล
            now_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            order_code = f"POS-{now_str}"

            current_emp = getattr(request.user, 'employee', None)

            order = POSOrder.objects.create(
                code=order_code,
                employee=current_emp,
                total_amount=total_amount,
                payment_method='CASH'
            )

            # 2. วนลูปสินค้า -> บันทึก และ ตัดสต็อก
            for item in cart:
                product = Product.objects.get(id=item['id'])
                POSOrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    quantity=item['qty'],
                    price=item['price']
                )
                product.stock_qty -= item['qty']
                product.save()

            # 3. 💰 ลงบัญชี "รายรับ" อัตโนมัติ (New!)
            Income.objects.create(
                title=f"รายรับจากการขายบิล {order_code}",
                amount=total_amount,
                date=datetime.date.today(),
                pos_order=order, # เชื่อมโยงกลับไปหาบิลได้
                note="บันทึกอัตโนมัติจากระบบ POS"
            )

            return JsonResponse({'success': True, 'order_code': order_code})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid Request'})

# --- 3. ระบบใบเสนอราคา (Quotation) ✅ มาใหม่ ---

@login_required
def quotation_list(request):
    # ดึงใบเสนอราคาทั้งหมด เรียงจากใหม่ไปเก่า
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
                status='DRAFT' # สร้างเสร็จให้เป็นสถานะ ร่าง ไว้ก่อน
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

            # อัปเดตยอดรวมท้ายบิล
            quotation.subtotal = total_val
            quotation.grand_total = total_val # (ยังไม่รวมภาษี ไว้ค่อยทำเพิ่มได้ครับ)
            quotation.save()

            return JsonResponse({'success': True, 'code': code})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # กรณีเปิดหน้าเว็บ (GET)
    customers = Customer.objects.all()
    products = Product.objects.filter(is_active=True)
    return render(request, 'sales/quotation_form.html', {
        'customers': customers,
        'products': products
    })

# ✅ เพิ่มฟังก์ชันนี้ต่อท้ายสุดของไฟล์
@login_required
def quotation_print(request, quote_id):
    # ดึงใบเสนอราคาตาม ID ที่ระบุ
    quote = get_object_or_404(Quotation, id=quote_id)

    # ดึงข้อมูลบริษัท (เอามาแปะหัวบิล)
    from master_data.models import CompanyInfo
    company = CompanyInfo.objects.first()

    context = {
        'quote': quote,
        'company': company,
        'items': quote.items.all() # ดึงรายการสินค้าในบิล
    }
    return render(request, 'sales/quotation_print.html', context)

@login_required
def pos_print_slip(request, order_code):
    # ดึงข้อมูลบิลจากเลขที่บิล (Code)
    order = get_object_or_404(POSOrder, code=order_code)

    # ดึงข้อมูลร้านค้า (Company Info)
    from master_data.models import CompanyInfo
    company = CompanyInfo.objects.first()

    context = {
        'order': order,
        'items': order.items.all(),
        'company': company,
    }
    return render(request, 'sales/slip_print.html', context)

# ✅ ฟังก์ชันส่งออกรายงาน Excel
@login_required
def export_sales_excel(request):
    # 1. สร้างสมุดงาน Excel เปล่าๆ
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    # 2. สร้างหัวตาราง (Header)
    headers = ["วันที่/เวลา", "เลขที่บิล", "พนักงานขาย", "วิธีชำระ", "ยอดขาย (บาท)"]
    ws.append(headers)

    # 3. ดึงข้อมูลจากฐานข้อมูล (POSOrder)
    # เรียงจากล่าสุดไปเก่าสุด
    orders = POSOrder.objects.all().order_by('-created_at')

    total_sales = 0

    # 4. วนลูปเขียนข้อมูลทีละแถว
    for order in orders:
        # แปลงวันที่เป็น text สวยๆ (ปี-เดือน-วัน เวลา)
        date_str = order.created_at.strftime('%Y-%m-%d %H:%M')

        # ชื่อพนักงาน (เช็คก่อนว่ามีไหม)
        emp_name = order.employee.first_name if order.employee else "Admin/Unkown"

        ws.append([
            date_str,
            order.code,
            emp_name,
            order.payment_method,
            order.total_amount
        ])
        total_sales += order.total_amount

    # 5. เพิ่มบรรทัดสรุปยอดรวม
    ws.append([]) # เว้นบรรทัด
    ws.append(["", "", "", "รวมทั้งสิ้น:", total_sales])

    # 6. ส่งไฟล์กลับไปให้คนกดดาวน์โหลด
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Sales_Report.xlsx"'
    wb.save(response)

    return response