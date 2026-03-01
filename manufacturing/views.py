from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Max
import datetime

from .models import ProductionOrder, BOM
from master_data.models import CompanyInfo
from inventory.models import Product
from purchasing.models import PurchaseOrder, PurchaseOrderItem

@login_required
def ppo_prepare(request):
    """ หน้าเตรียมการสั่งซื้อ (PPO) - ส่งข้อมูลสินค้าแบบละเอียด """
    fg_products = Product.objects.filter(product_type='FG', is_active=True)
    fg_id = request.GET.get('fg_id')
    fg_qty = request.GET.get('fg_qty', 1)
    
    ppo_code = ""
    materials_by_supplier = {}
    
    if fg_id:
        now = datetime.datetime.now()
        prefix = f"PPO-{now.strftime('%y%m')}"
        last_ppo = PurchaseOrder.objects.filter(ppo_ref__startswith=prefix).aggregate(Max('ppo_ref'))['ppo_ref__max']
        seq = 1
        if last_ppo:
            try: seq = int(last_ppo.split('-')[-1]) + 1
            except: seq = 1
        ppo_code = f"{prefix}-{seq:03d}"
        
        bom = BOM.objects.filter(product_id=fg_id).first()
        if bom:
            for item in bom.items.all():
                total_needed = float(item.quantity) * int(fg_qty)
                supplier = item.raw_material.supplier
                sup_id = supplier.id if supplier else "none"
                sup_name = supplier.name if supplier else "ไม่ได้ระบุร้านค้า"
                
                if sup_id not in materials_by_supplier:
                    materials_by_supplier[sup_id] = {'name': sup_name, 'items': []}
                
                materials_by_supplier[sup_id]['items'].append({
                    'product_id': item.raw_material.id,
                    'product_name': item.raw_material.name,
                    'product_code': item.raw_material.code,
                    'qty': total_needed,
                    'cost': float(item.raw_material.cost_price),
                    'total': total_needed * float(item.raw_material.cost_price)
                })
        else:
            messages.warning(request, "ไม่พบสูตรผลิตสำหรับสินค้านี้")

    return render(request, 'manufacturing/ppo_prepare.html', {
        'fg_products': fg_products,
        'ppo_code': ppo_code,
        'materials_by_supplier': materials_by_supplier,
        'fg_qty': fg_qty,
        'selected_fg': int(fg_id) if fg_id else None
    })

# ★ เติมส่วนที่ขาดหายไปเพื่อให้ URL ทำงานได้ ★

@login_required
def production_detail(request, pk):
    """ แสดงรายละเอียดใบสั่งผลิต """
    order = get_object_or_404(ProductionOrder, pk=pk)
    return render(request, 'manufacturing/production_detail.html', {'order': order})

@login_required
def generate_pos_from_production(request, pk):
    """ ฟังก์ชันสร้าง PO อัตโนมัติจากใบสั่งผลิต (ถ้าจำเป็นต้องใช้) """
    messages.info(request, "ฟังก์ชันนี้กำลังอยู่ระหว่างการพัฒนาเพิ่มเติม")
    return redirect('ppo_prepare')

@login_required
def production_print(request, po_id):
    po = get_object_or_404(ProductionOrder, id=po_id)
    bom = BOM.objects.filter(product=po.product).first()
    company = CompanyInfo.objects.first()
    return render(request, 'manufacturing/production_print.html', {'po': po, 'bom': bom, 'company': company})