from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max
from django.contrib import messages
from django.forms import inlineformset_factory
from django.utils import timezone
import datetime
import json

from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderPayment, PurchasePreparation
from .forms import PurchaseOrderForm, PurchaseOrderItemFormSet, PurchaseOrderItemForm
from master_data.models import CompanyInfo
from inventory.models import Product
from manufacturing.models import BOM

@login_required
def purchasing_dashboard(request):
    pos = PurchaseOrder.objects.all()
    draft_count = pos.filter(status='DRAFT').count()
    pending_payment_pos = pos.filter(payment_status__in=['PENDING', 'DEPOSIT'], status='APPROVED')
    pending_payment_count = pending_payment_pos.count()
    pending_payment_amount = pending_payment_pos.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    deposit_paid = PurchaseOrderPayment.objects.filter(po__in=pending_payment_pos).aggregate(Sum('amount'))['amount__sum'] or 0
    actual_pending_amount = float(pending_payment_amount) - float(deposit_paid)

    pending_receipt_count = pos.filter(receipt_status__in=['PENDING', 'PARTIAL'], status='APPROVED').count()
    recent_pos = pos.order_by('-created_at')[:10] # โชว์แค่ 10 ใบในหน้าแรก

    context = {
        'draft_count': draft_count,
        'pending_payment_count': pending_payment_count,
        'pending_payment_amount': actual_pending_amount,
        'pending_receipt_count': pending_receipt_count,
        'recent_pos': recent_pos,
    }
    return render(request, 'purchasing/purchasing_dashboard.html', context)

# ==========================================
# 🌟 ระบบดูใบสั่งซื้อทั้งหมด (PO List) 🌟
# ==========================================
@login_required
def po_list(request):
    """ หน้าดูรายการใบสั่งซื้อทั้งหมด """
    # ดึงข้อมูลใบสั่งซื้อทั้งหมด เรียงจากใหม่ไปเก่า
    pos = PurchaseOrder.objects.all().order_by('-created_at')
    return render(request, 'purchasing/po_list.html', {'pos': pos})


@login_required
def po_create(request):
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

            now = datetime.datetime.now()
            prefix = f"PO-{now.strftime('%y%m')}"
            last_po = PurchaseOrder.objects.filter(code__startswith=prefix).aggregate(Max('code'))['code__max']
            seq = 1
            if last_po:
                try: seq = int(last_po.split('-')[-1]) + 1
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

            messages.success(request, f"✅ สร้างใบสั่งซื้อ {po.code} เรียบร้อยแล้ว!")
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
    po = get_object_or_404(PurchaseOrder, id=po_id)
    company = CompanyInfo.objects.first()
    return render(request, 'purchasing/po_print.html', {'po': po, 'company': company})

@login_required
def po_edit(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    fg_products = Product.objects.filter(product_type='FG', is_active=True)

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
        'fg_products': fg_products
    })

@login_required
def po_payment(request, po_id):
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
    ppos = PurchasePreparation.objects.all().order_by('-id')
    return render(request, 'purchasing/ppo_list.html', {'ppos': ppos})

@login_required
def ppo_detail(request, pk):
    ppo = get_object_or_404(PurchasePreparation, pk=pk)
    materials_by_supplier = {}
    
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
        materials_by_supplier[sup_id]['items'] = list(materials_by_supplier[sup_id]['items'].values())

    return render(request, 'purchasing/ppo_detail.html', {
        'ppo': ppo,
        'materials_by_supplier': materials_by_supplier
    })