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
from django.forms.models import inlineformset_factory

from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderPayment, PurchasePreparation, OverseasPO
from .forms import PurchaseOrderForm, PurchaseOrderItemFormSet, PurchaseOrderItemForm
from master_data.models import CompanyInfo
from inventory.models import Product
from manufacturing.models import BOM

# ==========================================
# 🛡️ ระบบนายทวาร (Gatekeeper) แบ่งสิทธิ์การทำงาน
# ==========================================
def can_view_and_pay(user):
    if user.is_superuser: 
        return True
    
    user_groups = list(user.groups.values_list('name', flat=True))
    if 'Purchasing' in user_groups or 'Accounting' in user_groups or 'Executive' in user_groups:
        return True
        
    if hasattr(user, 'employee') and user.employee:
        dept = user.employee.department.name if user.employee.department else ''
        if 'จัดซื้อ' in dept or 'Purchasing' in dept or 'บัญชี' in dept or 'Accounting' in dept:
            return True
            
    return False

def can_create_po(user):
    if user.is_superuser: 
        return True
    
    user_groups = list(user.groups.values_list('name', flat=True))
    if 'Purchasing' in user_groups or 'Executive' in user_groups:
        return True
        
    if hasattr(user, 'employee') and user.employee:
        dept = user.employee.department.name if user.employee.department else ''
        if 'จัดซื้อ' in dept or 'Purchasing' in dept:
            return True
            
    return False

def check_is_approver(user):
    if user.is_superuser:
        return True
        
    user_groups = list(user.groups.values_list('name', flat=True))
    if 'Executive' in user_groups:
        return True
        
    if hasattr(user, 'employee') and user.employee:
        job_title = user.employee.position.title.lower() if user.employee.position else ""
        rank = user.employee.business_rank.lower() if user.employee.business_rank else ""
        
        if 'manager' in job_title or 'ผู้จัดการ' in job_title or 'director' in job_title or 'ผู้อำนวยการ' in job_title:
            return True
        if rank in ['manager', 'director', 'executive']:
            return True
            
    return False

# ==========================================
# 🛒 ระบบจัดซื้อ (Purchasing)
# ==========================================
@login_required
def purchasing_dashboard(request):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เข้าถึงระบบจัดซื้อ")
        return redirect('dashboard')

    pos = PurchaseOrder.objects.all()
    draft_count = pos.filter(status='DRAFT').count()
    pending_payment_pos = pos.filter(payment_status__in=['PENDING', 'DEPOSIT'], status='APPROVED')
    pending_payment_count = pending_payment_pos.count()
    pending_payment_amount = pending_payment_pos.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    deposit_paid = PurchaseOrderPayment.objects.filter(po__in=pending_payment_pos).aggregate(Sum('amount'))['amount__sum'] or 0
    actual_pending_amount = float(pending_payment_amount) - float(deposit_paid)

    pending_receipt_count = pos.filter(receipt_status__in=['PENDING', 'PARTIAL'], status='APPROVED').count()
    recent_pos = pos.order_by('-created_at')[:10]

    # 🌟 เช็กสิทธิ์ว่าเป็นผู้จัดการ (ผู้อนุมัติ) หรือไม่ เพื่อเปิดฟังก์ชันคลิกที่การ์ด
    is_approver = check_is_approver(request.user)

    context = {
        'draft_count': draft_count,
        'pending_payment_count': pending_payment_count,
        'pending_payment_amount': actual_pending_amount,
        'pending_receipt_count': pending_receipt_count,
        'recent_pos': recent_pos,
        'is_approver': is_approver, # 🌟 ส่งค่านี้ไปบอกหน้าเว็บ
    }
    return render(request, 'purchasing/purchasing_dashboard.html', context)

@login_required
def po_list(request):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    search_query = request.GET.get('q', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')

    pos = PurchaseOrder.objects.all().order_by('-created_at')

    if search_query:
        pos = pos.filter(Q(code__icontains=search_query) | Q(supplier__name__icontains=search_query))

    if status_filter:
        pos = pos.filter(status=status_filter)

    if payment_filter:
        pos = pos.filter(payment_status=payment_filter)

    if start_date:
        pos = pos.filter(date__gte=start_date)
    if end_date:
        pos = pos.filter(date__lte=end_date)

    context = {
        'pos': pos,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
        'status_filter': status_filter,
        'payment_filter': payment_filter
    }
    return render(request, 'purchasing/po_list.html', context)

@login_required
def po_create(request):
    if not can_create_po(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์สร้างใบสั่งซื้อ (สงวนไว้สำหรับแผนกจัดซื้อ)")
        return redirect('purchasing_dashboard')

    ppo_ref = request.GET.get('ppo_ref', '')
    supplier_id = request.GET.get('supplier_id')
    items_json = request.GET.get('items_data', '[]')
    
    initial_items = []
    
    if items_json:
        try:
            data = json.loads(items_json)
            for item in data:
                initial_items.append({
                    'product': item['id'],
                    'quantity': item['qty'],
                    'unit_cost': item['cost'],
                    'total_cost': item['total']
                })
        except:
            pass

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            po = form.save(commit=False)
            po.status = 'DRAFT'
            now = datetime.datetime.now()
            thai_year = (now.year + 543) % 100
            prefix = f"PO-{thai_year:02d}{now.strftime('%m')}"
            
            last_po = PurchaseOrder.objects.filter(code__startswith=prefix).aggregate(Max('code'))['code__max']
            seq = 1
            if last_po:
                try: 
                    seq = int(last_po.split('-')[-1]) + 1
                except: seq = 1
            po.code = f"{prefix}-{seq:03d}"
            
            if ppo_ref:
                po.ppo_ref = ppo_ref

            po.buyer = getattr(request.user, 'employee', None)
            po.save()

            formset.instance = po
            formset.save()

            total = sum(item.total_cost for item in po.items.all() if item.total_cost)
            po.total_amount = total
            po.save()

            messages.success(request, f"✅ สร้างใบสั่งซื้อ {po.code} เรียบร้อยแล้ว (รอดำเนินการอนุมัติ)!")
            return redirect('purchasing_dashboard')
        else:
            messages.error(request, "❌ กรุณาตรวจสอบข้อมูลให้ครบถ้วน")
    else:
        form = PurchaseOrderForm(initial={
            'status': 'DRAFT',
            'supplier': supplier_id if supplier_id else None
        })
        
        extra_rows = len(initial_items) if initial_items else 1
        PurchaseOrderItemFormSetDynamic = inlineformset_factory(
            PurchaseOrder, PurchaseOrderItem, 
            form=PurchaseOrderItemForm, 
            extra=extra_rows, 
            can_delete=True
        )
        formset = PurchaseOrderItemFormSetDynamic(initial=initial_items if initial_items else None)

    fg_products = Product.objects.filter(product_type='FG', is_active=True)

    return render(request, 'purchasing/po_create.html', {
        'form': form,
        'formset': formset,
        'ppo_ref': ppo_ref,
        'fg_products': fg_products
    })

@login_required
def po_print(request, po_id):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
        
    po = get_object_or_404(PurchaseOrder, id=po_id)
    company = CompanyInfo.objects.first()
    return render(request, 'purchasing/po_print.html', {'po': po, 'company': company})

@login_required
def po_edit(request, po_id):
    if not can_create_po(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์แก้ไขใบสั่งซื้อ")
        return redirect('purchasing_dashboard')

    po = get_object_or_404(PurchaseOrder, id=po_id)
    fg_products = Product.objects.filter(product_type='FG', is_active=True)

    is_approver = check_is_approver(request.user)

    PurchaseOrderItemFormSetEdit = inlineformset_factory(
        PurchaseOrder, PurchaseOrderItem, 
        form=PurchaseOrderItemForm, 
        extra=1 if not po.items.exists() else 0,
        can_delete=True
    )

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=po)
        formset = PurchaseOrderItemFormSetEdit(request.POST, instance=po)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            total = sum(item.total_cost for item in po.items.all() if item.total_cost)
            po.total_amount = total
            po.save()

            messages.success(request, f"✅ แก้ไขและบันทึกใบสั่งซื้อ {po.code} เรียบร้อยแล้ว!")
            return redirect('purchasing_dashboard')
        else:
            messages.error(request, "❌ กรุณาตรวจสอบข้อมูลให้ครบถ้วน")
    else:
        form = PurchaseOrderForm(instance=po)
        formset = PurchaseOrderItemFormSetEdit(instance=po)

    return render(request, 'purchasing/po_create.html', {
        'form': form,
        'formset': formset,
        'po': po, 
        'fg_products': fg_products,
        'is_approver': is_approver
    })

@login_required
def po_payment(request, po_id):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์เข้าถึงหน้าระบบจ่ายเงิน")
        return redirect('dashboard')

    po = get_object_or_404(PurchaseOrder, id=po_id)
    payments = po.payments.all().order_by('-created_at')
    total_paid = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    balance = float(po.total_amount) - float(total_paid)

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0').replace(',', '')
        try:
            amount = float(amount_str)
        except ValueError:
            amount = 0
        
        if amount > 0 and amount <= balance:
            PurchaseOrderPayment.objects.create(
                po=po,
                payment_date=request.POST.get('payment_date', timezone.now().date()),
                amount=amount,
                payment_method=request.POST.get('payment_method', 'โอนเงิน'),
                reference_no=request.POST.get('reference_no', ''),
                note=request.POST.get('note', '')
            )
            
            new_total_paid = float(total_paid) + float(amount)
            if new_total_paid >= float(po.total_amount):
                po.payment_status = 'PAID'
            else:
                po.payment_status = 'DEPOSIT'
            po.save()
            
            messages.success(request, f"✅ บันทึกชำระเงิน {amount:,.2f} บาท สำเร็จ!")
            return redirect('po_payment', po_id=po.id)
        else:
            messages.error(request, "❌ จำนวนเงินไม่ถูกต้อง หรือเกินยอดคงค้าง")
            
    return render(request, 'purchasing/po_payment.html', {
        'po': po,
        'payments': payments,
        'total_paid': total_paid,
        'balance': balance
    })

@login_required
def ppo_list(request):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    ppos = PurchasePreparation.objects.all().order_by('-id')
    
    for ppo in ppos:
        total_amount = 0
        for job in ppo.production_orders.all():
            bom = BOM.objects.filter(product=job.product).first()
            if bom:
                for item in bom.items.all():
                    qty = float(item.quantity)
                    cost = float(item.raw_material.cost_price)
                    total_amount += (qty * cost)
        ppo.total_estimated_cost = total_amount
        
    return render(request, 'purchasing/ppo_list.html', {'ppos': ppos})

@login_required
def ppo_detail(request, pk):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    ppo = get_object_or_404(PurchasePreparation, pk=pk)
    materials_by_supplier = {}
    grand_total = 0 
    
    for job in ppo.production_orders.all():
        bom = BOM.objects.filter(product=job.product).first()
        if bom:
            for item in bom.items.all():
                total_needed = float(item.quantity)
                supplier = item.raw_material.supplier
                sup_id = supplier.id if supplier else "none"
                sup_name = supplier.name if supplier else "ไม่ได้ระบุร้านค้า"
                mat_id = item.raw_material.id
                
                if sup_id not in materials_by_supplier:
                    materials_by_supplier[sup_id] = {'name': sup_name, 'items': {}}
                
                if mat_id not in materials_by_supplier[sup_id]['items']:
                    materials_by_supplier[sup_id]['items'][mat_id] = {
                        'product_id': item.raw_material.id,
                        'product_name': item.raw_material.name,
                        'product_code': item.raw_material.code,
                        'qty': 0,
                        'cost': float(item.raw_material.cost_price),
                        'total': 0
                    }
                
                materials_by_supplier[sup_id]['items'][mat_id]['qty'] += total_needed
                materials_by_supplier[sup_id]['items'][mat_id]['total'] = materials_by_supplier[sup_id]['items'][mat_id]['qty'] * materials_by_supplier[sup_id]['items'][mat_id]['cost']

    for sup_id in materials_by_supplier:
        sup_total = sum(item['total'] for item in materials_by_supplier[sup_id]['items'].values())
        materials_by_supplier[sup_id]['supplier_total'] = sup_total
        grand_total += sup_total
        
        materials_by_supplier[sup_id]['items'] = list(materials_by_supplier[sup_id]['items'].values())

    created_pos = PurchaseOrder.objects.filter(ppo_ref=ppo.code)
    created_supplier_ids = [str(po.supplier_id) if po.supplier_id else "none" for po in created_pos]

    for sup_id in materials_by_supplier:
        materials_by_supplier[sup_id]['is_po_created'] = str(sup_id) in created_supplier_ids

    return render(request, 'purchasing/ppo_detail.html', {
        'ppo': ppo,
        'materials_by_supplier': materials_by_supplier,
        'grand_total': grand_total 
    })

@login_required
def po_approve(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    
    is_approver = check_is_approver(request.user)
    
    if is_approver and po.status == 'DRAFT':
        po.status = 'APPROVED'
        po.save()
        messages.success(request, f"✅ อนุมัติใบสั่งซื้อ {po.code} เรียบร้อยแล้ว")
    else:
        messages.error(request, "❌ คุณไม่มีสิทธิ์อนุมัติ หรือสถานะเอกสารไม่ถูกต้อง")
    return redirect('po_list')

@login_required
def po_cancel(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    
    is_approver = check_is_approver(request.user)
    
    if is_approver and po.status == 'DRAFT':
        po.status = 'CANCELLED'
        po.save()
        messages.warning(request, f"⚠️ ยกเลิกใบสั่งซื้อ {po.code} เรียบร้อยแล้ว")
    else:
        messages.error(request, "❌ คุณไม่มีสิทธิ์ยกเลิก หรือสถานะเอกสารไม่ถูกต้อง")
    return redirect('po_list')


# ==========================================
# ✈️ ระบบสั่งซื้อต่างประเทศ (Overseas PO Tracker)
# ==========================================
@login_required
def overseas_po_list(request):
    if not can_view_and_pay(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์เข้าถึงระบบจัดซื้อต่างประเทศ")
        return redirect('purchasing_dashboard')
        
    query = request.GET.get('q', '')
    if query:
        overseas_pos = OverseasPO.objects.filter(Q(supplier_name__icontains=query) | Q(pi_number__icontains=query)).order_by('-id')
    else:
        overseas_pos = OverseasPO.objects.all().order_by('-id')
        
    return render(request, 'purchasing/overseas_po_list.html', {'overseas_pos': overseas_pos, 'query': query})

@login_required
def overseas_po_save(request):
    if not can_create_po(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์จัดการข้อมูลจัดซื้อ")
        return redirect('overseas_po_list')

    if request.method == 'POST':
        po_id = request.POST.get('po_id')
        
        supplier_name = request.POST.get('supplier_name')
        pi_number = request.POST.get('pi_number')
        total_amount = request.POST.get('total_amount', '0').replace(',', '')
        
        deposit_date = request.POST.get('deposit_date') or None
        deposit_amount = request.POST.get('deposit_amount', '0').replace(',', '')
        balance_date = request.POST.get('balance_date') or None
        balance_amount = request.POST.get('balance_amount', '0').replace(',', '')
        
        is_fully_paid = request.POST.get('is_fully_paid') == 'on'
        doc_fe = request.POST.get('doc_fe') == 'on'
        doc_bl = request.POST.get('doc_bl') == 'on'
        doc_pl = request.POST.get('doc_pl') == 'on'
        doc_ci = request.POST.get('doc_ci') == 'on'

        if po_id: 
            po = get_object_or_404(OverseasPO, id=po_id)
        else: 
            po = OverseasPO()
            
        po.supplier_name = supplier_name
        po.pi_number = pi_number
        po.total_amount = total_amount or 0
        po.deposit_date = deposit_date
        po.deposit_amount = deposit_amount or 0
        po.balance_date = balance_date
        po.balance_amount = balance_amount or 0
        po.is_fully_paid = is_fully_paid
        po.doc_fe = doc_fe
        po.doc_bl = doc_bl
        po.doc_pl = doc_pl
        po.doc_ci = doc_ci
        po.save()
        
        messages.success(request, f"✅ บันทึกรายการ PI: {pi_number} เรียบร้อยแล้ว")
    return redirect('overseas_po_list')
    
@login_required
def overseas_po_delete(request, pk):
    if not can_create_po(request.user):
        messages.error(request, "❌ คุณไม่มีสิทธิ์ลบข้อมูล")
        return redirect('overseas_po_list')
        
    po = get_object_or_404(OverseasPO, pk=pk)
    po.delete()
    messages.success(request, "🗑️ ลบรายการสั่งซื้อต่างประเทศเรียบร้อยแล้ว")
    return redirect('overseas_po_list')