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

from .models import Quotation, QuotationItem, POSOrder, POSOrderItem, Invoice, UpsaleCategory, UpsaleCatalog, QuotationUpsale
from inventory.models import Product, Category
from master_data.models import Customer, CompanyInfo
from hr.models import Employee
from .forms import QuotationForm

# 🌟 เพิ่มการดึง Model ProductionStatus เพื่อนับจำนวนแผนกสำหรับทำ Progress Bar 🌟
from manufacturing.models import ProductionOrder, Salesperson as MfgSalesperson, Branch as MfgBranch, ProductionStatus

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
        dept_name = current_emp.department.name if current_emp.department else ""
        if 'บัญชี' in dept_name or 'Accounting' in dept_name:
            return Employee.objects.all(), "Accounting View"

        rank = current_emp.business_rank.lower() if current_emp.business_rank else ""
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

    if hasattr(user, 'employee') and user.employee:
        dept_name = user.employee.department.name if user.employee.department else ""
        rank = user.employee.business_rank.lower() if user.employee.business_rank else ""
        job_title = user.employee.position.title.lower() if user.employee.position else ""

        if 'บัญชี' in dept_name or 'Accounting' in dept_name:
            return model_class.objects.all()
        if rank in ['manager', 'director'] or 'manager' in job_title:
            return model_class.objects.all()

    return model_class.objects.filter(employee__in=target_employees)

def is_sales_authorized(user):
    if user.is_superuser:
        return True

    user_groups = list(user.groups.values_list('name', flat=True))
    if 'Sales' in user_groups:
        return True

    if hasattr(user, 'employee') and user.employee:
        dept = user.employee.department.name if user.employee.department else ''
        if 'ขาย' in dept or 'Sales' in dept:
            return True

    return False

@login_required
def sales_dashboard(request):
    if not is_sales_authorized(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เข้าถึงภาพรวมฝ่ายขาย")
        return redirect('dashboard')

    target_employees, scope_title = get_target_employees(request.user)

    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else today
    end_date = parse_date(end_date_str) if end_date_str else today

    pos_qs = get_sales_queryset(POSOrder, request.user, target_employees).filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    inv_qs = get_sales_queryset(Invoice, request.user, target_employees).filter(date__gte=start_date, date__lte=end_date)

    pos_total = pos_qs.filter(status='PAID').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    inv_total = inv_qs.filter(status='PAID').aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_sales_amount = pos_total + inv_total

    pos_today = get_sales_queryset(POSOrder, request.user, target_employees).filter(created_at__date=today)
    inv_today = get_sales_queryset(Invoice, request.user, target_employees).filter(date=today)
    total_orders_today = pos_today.count() + inv_today.count()

    qt_all_qs = get_sales_queryset(Quotation, request.user, target_employees)

    pending_approval_quotes = qt_all_qs.filter(status='DRAFT').count()
    pending_closing_quotes = qt_all_qs.filter(status='APPROVED', is_deposit_paid=False).count()
    in_production_quotes = qt_all_qs.filter(status='APPROVED', is_deposit_paid=True).count()

    pending_production_quotes = qt_all_qs.filter(
        status='APPROVED', is_deposit_paid=True, production_orders__isnull=True
    ).count()

    pos_team = pos_qs.filter(status='PAID').values('employee__department__name').annotate(total=Sum('total_amount'))
    inv_team = inv_qs.filter(status='PAID').values('employee__department__name').annotate(total=Sum('grand_total'))

    team_sales_dict = {}
    for p in pos_team:
        dept = p['employee__department__name'] or 'ไม่ระบุทีม'
        team_sales_dict[dept] = team_sales_dict.get(dept, 0) + float(p['total'] or 0)
    for i in inv_team:
        dept = i['employee__department__name'] or 'ไม่ระบุทีม'
        team_sales_dict[dept] = team_sales_dict.get(dept, 0) + float(i['total'] or 0)

    sorted_teams = sorted(team_sales_dict.items(), key=lambda x: x[1], reverse=True)
    chart_labels = [x[0] for x in sorted_teams]
    chart_data = [x[1] for x in sorted_teams]

    recent_pos = list(pos_qs.order_by('-created_at')[:10])
    recent_inv = list(inv_qs.order_by('-created_at')[:10])
    combined_sales = sorted(recent_pos + recent_inv, key=lambda x: x.created_at, reverse=True)[:10]

    context = {
        'total_sales_today': total_sales_amount,
        'total_orders_today': total_orders_today,
        'pending_approval_quotes': pending_approval_quotes,
        'pending_closing_quotes': pending_closing_quotes,
        'in_production_quotes': in_production_quotes,
        'pending_production_quotes': pending_production_quotes,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'recent_sales': combined_sales,
        'scope_title': scope_title,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    }
    return render(request, 'sales/dashboard.html', context)

@login_required
def api_dashboard_data(request):
    if not is_sales_authorized(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    target_employees, _ = get_target_employees(request.user)

    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else today
    end_date = parse_date(end_date_str) if end_date_str else today

    pos_qs = get_sales_queryset(POSOrder, request.user, target_employees).filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    inv_qs = get_sales_queryset(Invoice, request.user, target_employees).filter(date__gte=start_date, date__lte=end_date)

    pos_total = pos_qs.filter(status='PAID').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    inv_total = inv_qs.filter(status='PAID').aggregate(Sum('grand_total'))['grand_total__sum'] or 0
    total_sales_amount = float(pos_total + inv_total)

    pos_today = get_sales_queryset(POSOrder, request.user, target_employees).filter(created_at__date=today)
    inv_today = get_sales_queryset(Invoice, request.user, target_employees).filter(date=today)
    total_orders_today = pos_today.count() + inv_today.count()

    qt_all_qs = get_sales_queryset(Quotation, request.user, target_employees)

    pending_approval_quotes = qt_all_qs.filter(status='DRAFT').count()
    pending_closing_quotes = qt_all_qs.filter(status='APPROVED', is_deposit_paid=False).count()
    in_production_quotes = qt_all_qs.filter(status='APPROVED', is_deposit_paid=True).count()

    pending_production_quotes = qt_all_qs.filter(
        status='APPROVED', is_deposit_paid=True, production_orders__isnull=True
    ).count()

    pos_team = pos_qs.filter(status='PAID').values('employee__department__name').annotate(total=Sum('total_amount'))
    inv_team = inv_qs.filter(status='PAID').values('employee__department__name').annotate(total=Sum('grand_total'))

    team_sales_dict = {}
    for p in pos_team:
        dept = p['employee__department__name'] or 'ไม่ระบุทีม'
        team_sales_dict[dept] = team_sales_dict.get(dept, 0) + float(p['total'] or 0)
    for i in inv_team:
        dept = i['employee__department__name'] or 'ไม่ระบุทีม'
        team_sales_dict[dept] = team_sales_dict.get(dept, 0) + float(i['total'] or 0)

    sorted_teams = sorted(team_sales_dict.items(), key=lambda x: x[1], reverse=True)
    chart_labels = [x[0] for x in sorted_teams]
    chart_data = [x[1] for x in sorted_teams]

    recent_pos = list(pos_qs.order_by('-created_at')[:10])
    recent_inv = list(inv_qs.order_by('-created_at')[:10])
    combined_sales = sorted(recent_pos + recent_inv, key=lambda x: x.created_at, reverse=True)[:10]

    recent_sales_data = []
    for item in combined_sales:
        is_pos = 'POS' in item.code
        recent_sales_data.append({
            'time': item.created_at.strftime('%H:%M') if item.created_at.date() == timezone.now().date() else item.created_at.strftime('%d/%m/%Y'),
            'code': item.code,
            'is_pos': is_pos,
            'employee_name': item.employee.first_name if item.employee else '-',
            'employee_photo': item.employee.photo.url if item.employee and item.employee.photo else None,
            'employee_initial': item.employee.first_name[0] if item.employee and item.employee.first_name else '-',
            'amount': float(item.total_amount) if hasattr(item, 'total_amount') else float(item.grand_total)
        })

    return JsonResponse({
        'total_sales_today': total_sales_amount,
        'total_orders_today': total_orders_today,
        'pending_approval_quotes': pending_approval_quotes,
        'pending_closing_quotes': pending_closing_quotes,
        'in_production_quotes': in_production_quotes,
        'pending_production_quotes': pending_production_quotes,
        'recent_sales': recent_sales_data,
        'chart_labels': chart_labels,
        'chart_data': chart_data
    })

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
def record_deposit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    if request.method == 'POST':
        amount_str = request.POST.get('deposit_amount', '0').replace(',', '')
        try:
            amount = Decimal(amount_str)
        except:
            amount = Decimal(0)

        method = request.POST.get('deposit_method', 'TRANSFER')
        date_str = request.POST.get('deposit_date')
        next_url = request.POST.get('next')

        if amount > 0:
            qt.deposit_amount = amount
            qt.deposit_method = method
            if date_str:
                qt.deposit_date = parse_date(date_str)
            else:
                qt.deposit_date = timezone.now().date()
            qt.is_deposit_paid = True

            if 'deposit_slip' in request.FILES:
                qt.deposit_slip = request.FILES['deposit_slip']

            qt.save()
            messages.success(request, f"💰 บันทึกรับมัดจำ {amount:,.2f} บาท สำหรับใบเสนอราคา {qt.code} เรียบร้อยแล้ว")
        else:
            messages.error(request, "❌ จำนวนเงินมัดจำต้องมากกว่า 0")

        if next_url:
            return redirect(next_url)

    return redirect('quotation_edit', qt_id=qt.id)

@login_required
def create_job_order(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)

    if qt.production_orders.exists():
        messages.warning(request, f"⚠️ ใบเสนอราคา {qt.code} ถูกส่งสั่งผลิตไปแล้ว!")
        return redirect('quotation_list')

    if qt.is_deposit_paid and not qt.is_deposit_verified:
        messages.error(request, f"❌ ไม่สามารถส่งสั่งผลิตได้ บัญชียังไม่ได้ตรวจสอบสลิปเงินมัดจำของ {qt.code}")
        return redirect('quotation_list')

    first_item = qt.items.filter(product__isnull=False).first()
    if not first_item:
        messages.error(request, "❌ ไม่พบข้อมูลสินค้า (FG) ในใบเสนอราคา ไม่สามารถสร้างใบสั่งผลิตได้")
        return redirect('quotation_list')

    target_date_str = request.POST.get('target_date') if request.method == 'POST' else None
    target_date = parse_date(target_date_str) if target_date_str else None

    sales_obj = None
    branch_obj = None
    if qt.employee:
        emp_name = f"{qt.employee.first_name} {qt.employee.last_name}".strip()
        branch_name = qt.employee.department.name if qt.employee.department else "สำนักงานใหญ่"
        branch_obj, _ = MfgBranch.objects.get_or_create(name=branch_name)
        sales_obj, _ = MfgSalesperson.objects.get_or_create(name=emp_name, branch=branch_obj)

    job = ProductionOrder.objects.create(
        product=first_item.product,
        quotation_ref=qt,
        customer_name=qt.customer_name,
        note=f"อ้างอิงใบเสนอราคา: {qt.code}\n{qt.note}",
        salesperson=sales_obj,      
        branch=branch_obj,          
        delivery_date=target_date   
    )

    if first_item.product and first_item.product.standard_blueprint:
        job.blueprint_file = first_item.product.standard_blueprint
        job.save()

    messages.success(request, f"🏭 ส่งข้อมูลเปิดใบสั่งผลิต (Job Order: {job.code}) ให้แผนกปฏิบัติการเรียบร้อยแล้ว!")
    return redirect('quotation_list')

@login_required
def convert_quote_to_invoice(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    new_code = get_next_document_number()

    balance = qt.grand_total - qt.deposit_amount
    status = 'PAID' if balance <= 0 else 'UNPAID'

    invoice = Invoice.objects.create(
        code=new_code,
        quotation_ref=qt,
        date=timezone.now().date(),
        customer=qt.customer,
        employee=request.user.employee if hasattr(request.user, 'employee') else None,
        grand_total=qt.grand_total,
        deposit_amount=qt.deposit_amount,
        balance_amount=balance,
        status=status
    )
    qt.status = 'CONVERTED'
    qt.save()
    messages.success(request, f"✅ เปิดใบขายสินค้า {new_code} เรียบร้อย (ยอดคงค้างชำระ: {balance:,.2f} บาท)")
    return redirect('invoice_list')

@login_required
def pos_home(request):
    if not is_sales_authorized(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบ POS")
        return redirect('dashboard')

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
                if 'check_slip' in request.FILES:
                    order.check_slip = request.FILES['check_slip']

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
    item_total = Decimal('0.00')
    for item in items:
        item.item_name = item.product_name
        item.unit_price = item.price
        item.amount = item.total_price
        item_total += Decimal(str(item.amount))

    payment_note = "ชำระโดย: เงินสด (Cash)"
    if order.payment_method == 'TRANSFER':
        payment_note = "ชำระโดย: โอนเงิน (Bank Transfer)"
    elif order.payment_method == 'CHECK':
        payment_note = f"ชำระโดย: เช็คธนาคาร {order.check_bank} #{order.check_number}"

    grand_total = order.total_amount
    subtotal = grand_total / Decimal('1.07')
    tax_amount = grand_total - subtotal

    context = {
        'inv': order,
        'company': company,
        'items': items,
        'item_total': item_total,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'discount': Decimal('0.00'),
        'shipping_cost': Decimal('0.00'),
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
        if status_filter == 'PENDING_PRODUCTION':
            queryset = queryset.filter(is_deposit_paid=True, production_orders__isnull=True)
        elif status_filter == 'PENDING_CLOSING':
            queryset = queryset.filter(status='APPROVED', is_deposit_paid=False)
        elif status_filter == 'IN_PRODUCTION':
            queryset = queryset.filter(status='APPROVED', is_deposit_paid=True)
        else:
            queryset = queryset.filter(status=status_filter)

    prod_status_filter = request.GET.get('prod_status')
    if prod_status_filter:
        queryset = queryset.filter(production_orders__status=prod_status_filter)

    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(Q(code__icontains=search_query) | Q(customer_name__icontains=search_query))

    date_start = request.GET.get('start_date', '')
    date_end = request.GET.get('end_date', '')
    if date_start:
        queryset = queryset.filter(date__gte=date_start)
    if date_end:
        queryset = queryset.filter(date__lte=date_end)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    is_manager = False
    current_emp = getattr(request.user, 'employee', None)
    if request.user.is_superuser: is_manager = True
    elif current_emp:
        rank = current_emp.business_rank.lower()
        if rank in ['manager', 'director'] or 'manager' in current_emp.position.title.lower():
            is_manager = True

    # 🌟 นับจำนวนแผนกทั้งหมด ส่งไปทำ Progress Bar หน้าเว็บ 🌟
    total_departments_count = ProductionStatus.objects.count()

    return render(request, 'sales/quotation_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'is_manager': is_manager,
        'status_filter': status_filter,
        'prod_status_filter': prod_status_filter,
        'date_start': date_start,
        'date_end': date_end,
        'total_departments_count': total_departments_count
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

            if not qt.payment_terms:
                qt.payment_terms = "-ชำระเงินมัดจำ 50% ของยอดรวมเพื่อยืนยันการสั่งซื้อ ส่วนที่เหลือชำระก่อนการจัดส่ง"
            if not qt.note:
                qt.note = "-ไม่มี-"

            qt.save()
            messages.success(request, f"ร่างใบเสนอราคา {qt.code} เรียบร้อย กรุณาเพิ่มรายการสินค้า")
            return redirect('quotation_edit', qt_id=qt.id)
    else:
        form = QuotationForm(initial={'date': datetime.date.today(), 'valid_until': datetime.date.today() + datetime.timedelta(days=15)})
    return render(request, 'sales/quotation_form.html', {'form': form})


@login_required
def quotation_edit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)

    main_categories = Category.objects.all()
    products = Product.objects.filter(is_active=True, product_type='FG')

    products_list = []
    for p in products:
        products_list.append({
            'id': p.id,
            'name': p.name,
            'code': p.code,
            'sell_price': float(p.sell_price),
            'category_id': getattr(p, 'category_id', None)
        })

    upsale_categories = UpsaleCategory.objects.filter(is_active=True)
    upsale_catalogs = UpsaleCatalog.objects.filter(is_active=True)

    upsales_list = []
    for u in upsale_catalogs:
        upsales_list.append({
            'id': u.id,
            'name': u.name,
            'default_price': float(u.default_price),
            'category_id': u.category_id
        })

    main_item_total = sum(i.quantity * i.unit_price for i in qt.items.all())
    upsale_total = sum(u.total_price for u in qt.upsales.all())
    item_total = main_item_total + upsale_total

    balance_due = qt.grand_total - qt.deposit_amount

    if request.method == 'POST':
        if qt.status != 'DRAFT':
            messages.error(request, "❌ ไม่สามารถแก้ไขได้ เนื่องจากเอกสารนี้ถูกอนุมัติหรือล็อกไปแล้ว")
            return redirect('quotation_edit', qt_id=qt.id)

        if 'add_item' in request.POST:
            item_name = request.POST.get('item_name')
            qty = int(request.POST.get('quantity', 1))
            price = Decimal(request.POST.get('price', '0').replace(',', ''))
            product_id = request.POST.get('product_id')

            product_obj = None
            if product_id:
                try: product_obj = Product.objects.get(id=product_id)
                except Product.DoesNotExist: pass

            if item_name:
                QuotationItem.objects.create(
                    quotation=qt, product=product_obj, item_name=item_name, quantity=qty, unit_price=price
                )
                calculate_totals(qt)
            return redirect('quotation_edit', qt_id=qt.id)

        elif 'add_upsale' in request.POST:
            desc = request.POST.get('upsale_desc')
            qty = Decimal(request.POST.get('upsale_qty', '1'))
            price = Decimal(request.POST.get('upsale_price', '0').replace(',', ''))
            if desc:
                QuotationUpsale.objects.create(
                    quotation=qt, description=desc, quantity=qty, unit_price=price
                )
                calculate_totals(qt)
            return redirect('quotation_edit', qt_id=qt.id)

        elif 'delete_upsale' in request.POST:
            upsale_id = request.POST.get('upsale_id')
            try:
                QuotationUpsale.objects.filter(id=upsale_id).delete()
                calculate_totals(qt)
            except: pass
            return redirect('quotation_edit', qt_id=qt.id)

        elif 'update_info' in request.POST or 'finish_quote' in request.POST:
            qt.payment_terms = request.POST.get('payment_terms', '')
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

    return render(request, 'sales/quotation_edit.html', {
        'qt': qt,
        'main_categories': main_categories,
        'upsale_categories': upsale_categories,
        'products_json': json.dumps(products_list),
        'upsales_json': json.dumps(upsales_list),
        'item_total': item_total,
        'balance_due': balance_due
    })


def calculate_totals(qt):
    item_sum = sum(item.quantity * item.unit_price for item in qt.items.all())
    upsale_sum = sum(u.quantity * u.unit_price for u in qt.upsales.all())
    total_goods = item_sum + upsale_sum

    shipping = qt.shipping_cost if qt.shipping_cost else Decimal(0)
    discount = qt.discount if qt.discount else Decimal(0)

    grand_total = (total_goods + shipping) - discount
    if grand_total < 0: grand_total = 0

    qt.subtotal = grand_total / Decimal('1.07')
    qt.tax_amount = grand_total - qt.subtotal
    qt.grand_total = grand_total
    qt.save()

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(QuotationItem, pk=item_id)
    qt = item.quotation

    if qt.status != 'DRAFT':
        messages.error(request, "❌ ไม่สามารถลบรายการได้ เนื่องจากเอกสารนี้ถูกอนุมัติหรือล็อกไปแล้ว")
        return redirect('quotation_edit', qt_id=qt.id)

    item.delete()
    calculate_totals(qt)
    return redirect('quotation_edit', qt_id=qt.id)

@login_required
def quotation_clone(request, qt_id):
    old_qt = get_object_or_404(Quotation, pk=qt_id)
    now = datetime.datetime.now()
    thai_year = (now.year + 543) % 100
    prefix = f"QT-{thai_year:02d}{now.strftime('%m')}"
    last = Quotation.objects.filter(code__startswith=prefix).order_by('code').last()
    seq = int(last.code.split('-')[-1]) + 1 if last else 1
    new_code = f"{prefix}-{seq:03d}"

    new_qt = Quotation.objects.create(
        code=new_code,
        date=timezone.now().date(),
        valid_until=timezone.now().date() + datetime.timedelta(days=15),
        customer=old_qt.customer,
        customer_name=old_qt.customer_name,
        customer_address=old_qt.customer_address,
        customer_tax_id=old_qt.customer_tax_id,
        customer_phone=old_qt.customer_phone,
        employee=request.user.employee if hasattr(request.user, 'employee') else None,
        subtotal=old_qt.subtotal,
        discount=old_qt.discount,
        shipping_cost=old_qt.shipping_cost,
        tax_amount=old_qt.tax_amount,
        grand_total=old_qt.grand_total,
        status='DRAFT',
        payment_terms=old_qt.payment_terms if old_qt.payment_terms else "-ชำระเงินมัดจำ 50% ของยอดรวมเพื่อยืนยันการสั่งซื้อ ส่วนที่เหลือชำระก่อนการจัดส่ง",
        note=old_qt.note if old_qt.note else "-ไม่มี-",
    )

    for item in old_qt.items.all():
        QuotationItem.objects.create(
            quotation=new_qt, product=item.product, item_name=item.item_name,
            description=item.description, quantity=item.quantity, unit_price=item.unit_price, amount=item.amount
        )

    for upsale in old_qt.upsales.all():
        QuotationUpsale.objects.create(
            quotation=new_qt, description=upsale.description,
            quantity=upsale.quantity, unit_price=upsale.unit_price, total_price=upsale.total_price
        )

    messages.success(request, f"📋 คัดลอกเอกสารสำเร็จ! (คุณกำลังอยู่ในเอกสารใหม่ อ้างอิงข้อมูลจากใบเดิม {old_qt.code})")
    return redirect('quotation_edit', qt_id=new_qt.id)

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

    main_total = sum(item.quantity * item.unit_price for item in qt.items.all())
    upsale_total = sum(u.quantity * u.unit_price for u in qt.upsales.all())
    item_total = main_total + upsale_total

    return render(request, 'sales/quotation_print.html', {'qt': qt, 'company': company, 'item_total': item_total})

@login_required
def export_sales_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    ws.append(["วันที่", "เลขที่เอกสาร", "ประเภท", "ยอดขาย"])
    for p in POSOrder.objects.all():
        ws.append([p.created_at.strftime('%d/%m/%Y'), p.code, "POS", p.total_amount])
    for i in Invoice.objects.all():
        ws.append([i.date.strftime('%d/%m/%Y'), i.code, "Invoice", i.grand_total])
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
            'id': c.id, 'name': c.name, 'code': c.code, 'address': full_address, 'tax_id': c.tax_id, 'phone': c.phone
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
                name=name, code=code, phone=phone, tax_id=tax_id, address=address
            )
            return JsonResponse({
                'success': True,
                'customer': {
                    'id': customer.id, 'name': customer.name, 'address': customer.address,
                    'tax_id': customer.tax_id, 'phone': customer.phone
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
        'page_obj': page_obj, 'search_query': search_query,
        'start_date': start_date, 'end_date': end_date, 'status_filter': status_filter
    })

@login_required
def confirm_payment(request, doc_type, doc_id):
    if doc_type == 'pos':
        obj = get_object_or_404(POSOrder, id=doc_id)
    else:
        obj = get_object_or_404(Invoice, id=doc_id)

    obj.status = 'PAID'
    obj.save()
    messages.success(request, f"✅ ยืนยันรับชำระเงินเอกสาร {obj.code} ปิดการขายเรียบร้อยแล้ว!")
    return redirect('invoice_list')

@login_required
def record_invoice_payment(request, inv_id):
    inv = get_object_or_404(Invoice, pk=inv_id)
    if request.method == 'POST':
        method = request.POST.get('payment_method', 'TRANSFER')
        date_str = request.POST.get('payment_date')

        inv.payment_method = method
        if date_str:
            inv.payment_date = parse_date(date_str)
        else:
            inv.payment_date = timezone.now().date()

        if method == 'TRANSFER' and 'transfer_slip' in request.FILES:
            inv.transfer_slip = request.FILES['transfer_slip']
        elif method == 'CHECK':
            inv.check_number = request.POST.get('check_number', '')
            inv.check_bank = request.POST.get('check_bank', '')
            if 'check_slip' in request.FILES:
                inv.check_slip = request.FILES['check_slip']

        inv.status = 'PENDING'
        inv.save()
        messages.success(request, f"💰 บันทึกรับชำระเงินสำหรับเอกสาร {inv.code} เรียบร้อยแล้ว (รอการตรวจสอบยอดจากฝ่ายบัญชี)")

    return redirect('invoice_list')

@login_required
def invoice_print(request, inv_id):
    inv = get_object_or_404(Invoice, pk=inv_id)
    company = CompanyInfo.objects.first()

    items = []
    item_total = Decimal('0.00')
    subtotal = Decimal('0.00')
    tax_amount = Decimal('0.00')
    discount = Decimal('0.00')
    shipping_cost = Decimal('0.00')
    note = ""

    if inv.quotation_ref:
        qt = inv.quotation_ref
        items = list(qt.items.all())
        for item in items:
            item.amount = item.quantity * item.unit_price
            item_total += Decimal(str(item.amount))

        for u in qt.upsales.all():
            items.append(u)
            item_total += Decimal(str(u.total_price))

        subtotal = qt.subtotal
        tax_amount = qt.tax_amount
        discount = qt.discount
        shipping_cost = qt.shipping_cost
        note = qt.note

    if not getattr(inv, 'customer_name', None) and inv.quotation_ref:
            inv.customer_name = qt.customer_name
            inv.customer_address = qt.customer_address
            inv.customer_tax_id = qt.customer_tax_id
            inv.customer_phone = qt.customer_phone

    if not hasattr(inv, 'total_amount'):
        inv.total_amount = inv.grand_total

    if not hasattr(inv, 'deposit_amount'):
        inv.deposit_amount = Decimal('0.00')
        inv.balance_amount = inv.grand_total

    context = {
        'inv': inv, 'company': company, 'items': items,
        'item_total': item_total, 'subtotal': subtotal, 'tax_amount': tax_amount,
        'discount': discount, 'shipping_cost': shipping_cost, 'note': note,
    }
    return render(request, 'sales/invoice_print.html', context)

@login_required
def deposit_list(request):
    target_employees, _ = get_target_employees(request.user)
    qs = get_sales_queryset(Quotation, request.user, target_employees).filter(is_deposit_paid=True)

    search_query = request.GET.get('q', '')
    if search_query:
        qs = qs.filter(Q(code__icontains=search_query) | Q(customer_name__icontains=search_query))

    status_filter = request.GET.get('status')
    if status_filter == 'VERIFIED':
        qs = qs.filter(is_deposit_verified=True)
    elif status_filter == 'PENDING':
        qs = qs.filter(is_deposit_verified=False)

    qs = qs.order_by('-deposit_date', '-created_at')
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/deposit_list.html', {
        'page_obj': page_obj, 'search_query': search_query, 'status_filter': status_filter
    })

@login_required
def verify_deposit(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    qt.is_deposit_verified = True
    qt.save()
    messages.success(request, f"✅ บัญชียืนยันตรวจสอบยอดมัดจำของ {qt.code} เรียบร้อยแล้ว!")
    return redirect('deposit_list')

@login_required
def deposit_print(request, qt_id):
    qt = get_object_or_404(Quotation, pk=qt_id)
    company = CompanyInfo.objects.first()

    main_total = sum(item.quantity * item.unit_price for item in qt.items.all())
    upsale_total = sum(u.quantity * u.unit_price for u in qt.upsales.all())
    item_total = main_total + upsale_total

    balance_due = qt.grand_total - qt.deposit_amount
    return render(request, 'sales/deposit_print.html', {
        'qt': qt, 'company': company, 'item_total': item_total, 'balance_due': balance_due
    })