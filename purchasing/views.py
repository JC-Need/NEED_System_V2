from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max
from django.contrib import messages
from django.forms import inlineformset_factory
import datetime
import json  # เพิ่มสำหรับรับส่งข้อมูลรายการสินค้า

from .models import PurchaseOrder, PurchaseOrderItem
from .forms import PurchaseOrderForm, PurchaseOrderItemFormSet, PurchaseOrderItemForm
from master_data.models import CompanyInfo
from inventory.models import Product
from manufacturing.models import BOM

@login_required
def purchasing_dashboard(request):
    """ หน้า Dashboard สรุปภาพรวมการจัดซื้อ """
    pos = PurchaseOrder.objects.all()
    draft_count = pos.filter(status='DRAFT').count()
    pending_payment_pos = pos.filter(payment_status__in=['PENDING', 'DEPOSIT'], status='APPROVED')
    pending_payment_count = pending_payment_pos.count()
    pending_payment_amount = pending_payment_pos.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    pending_receipt_count = pos.filter(receipt_status__in=['PENDING', 'PARTIAL'], status='APPROVED').count()
    recent_pos = pos.order_by('-created_at')[:10]

    context = {
        'draft_count': draft_count,
        'pending_payment_count': pending_payment_count,
        'pending_payment_amount': pending_payment_amount,
        'pending_receipt_count': pending_receipt_count,
        'recent_pos': recent_pos,
    }
    return render(request, 'purchasing/purchasing_dashboard.html', context)

@login_required
def po_create(request):
    """ สร้างใบสั่งซื้อใหม่ (รองรับการดึงข้อมูลจาก PPO) """
    # 🌟 รับค่าอ้างอิง PPO และรายการสินค้าที่ส่งมาจากหน้า PPO 🌟
    ppo_ref = request.GET.get('ppo_ref', '')
    supplier_id = request.GET.get('supplier_id')
    items_json = request.GET.get('items_data', '[]')
    
    initial_items = []
    
    # ถ้ามีการส่งรายการสินค้ามาจากหน้า PPO ให้แปลงเป็นรายการเริ่มต้นในตาราง
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

            # --- ระบบรันเลขที่ PO อัตโนมัติ (PO-YYMM-XXX) ---
            now = datetime.datetime.now()
            prefix = f"PO-{now.strftime('%y%m')}"
            last_po = PurchaseOrder.objects.filter(code__startswith=prefix).aggregate(Max('code'))['code__max']
            seq = 1
            if last_po:
                try: seq = int(last_po.split('-')[-1]) + 1
                except: seq = 1
            po.code = f"{prefix}-{seq:03d}"
            
            # บันทึกข้อมูลอ้างอิง PPO (ถ้ามี)
            if ppo_ref:
                po.ppo_ref = ppo_ref

            po.buyer = getattr(request.user, 'employee', None)
            po.save()

            formset.instance = po
            formset.save()

            # คำนวณยอดเงินรวมสุทธิ
            total = sum(item.total_cost for item in po.items.all() if item.total_cost)
            po.total_amount = total
            po.save()

            messages.success(request, f"✅ สร้างใบสั่งซื้อ {po.code} เรียบร้อยแล้ว!")
            return redirect('purchasing_dashboard')
        else:
            messages.error(request, "❌ กรุณาตรวจสอบข้อมูลให้ครบถ้วน")
    else:
        # เปิดหน้าจอครั้งแรก: กำหนดค่าเริ่มต้นตามที่ส่งมาจาก PPO
        form = PurchaseOrderForm(initial={
            'status': 'DRAFT',
            'supplier': supplier_id if supplier_id else None
        })
        
        # จัดการ Formset ให้ยืดหยุ่นตามจำนวนสินค้าที่ดึงมา
        extra_rows = len(initial_items) if initial_items else 1
        PurchaseOrderItemFormSetDynamic = inlineformset_factory(
            PurchaseOrder, PurchaseOrderItem, 
            form=PurchaseOrderItemForm, 
            extra=extra_rows, 
            can_delete=True
        )
        formset = PurchaseOrderItemFormSetDynamic(initial=initial_items if initial_items else None)

    # ดึงรายชื่อสินค้า FG สำหรับ Dropdown คำนวณ BOM (เผื่อใช้หน้างาน)
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