from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Max, Count, Q
from django.db import transaction 
from django.http import JsonResponse
from django.core.paginator import Paginator # 🌟 Import ระบบแบ่งหน้า
import datetime
import calendar # 🌟 Import สำหรับคำนวณวันสิ้นเดือน
import json

from .models import ProductionOrder, BOM, Branch, Salesperson, ProductionStatus, ProductionTeam, DeliveryStatus, Transporter 
from master_data.models import CompanyInfo
from inventory.models import Product, InventoryDoc, StockMovement 
from purchasing.models import PurchaseOrder, PurchaseOrderItem, PurchasePreparation 
from .forms import BOMForm, BOMItemFormSet

# ==========================================
# 🌟 ระบบใบสั่งผลิต (Production Order) 🌟
# ==========================================
@login_required
def production_list(request):
    # 🌟 1. ตั้งค่าเริ่มต้น: ช่วงวันที่ของเดือนปัจจุบัน 🌟
    today = datetime.date.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    last_day = calendar.monthrange(today.year, today.month)[1]
    default_end = today.replace(day=last_day).strftime('%Y-%m-%d')

    # รับค่าจากกล่องค้นหา (ถ้าไม่มีให้ใช้ Default)
    start_date = request.GET.get('start_date', default_start)
    end_date = request.GET.get('end_date', default_end)
    search_q = request.GET.get('q', '')
    search_salesperson = request.GET.get('salesperson', '')
    search_team = request.GET.get('team', '')

    orders = ProductionOrder.objects.all().order_by('-id')

    # 🌟 2. กรองข้อมูลตามช่วงวันที่ และ คำค้นหา 🌟
    if start_date and end_date:
        orders = orders.filter(start_date__gte=start_date, start_date__lte=end_date)
        
    if search_q:
        orders = orders.filter(Q(code__icontains=search_q) | Q(customer_name__icontains=search_q))
    if search_salesperson:
        orders = orders.filter(salesperson_id=search_salesperson)
    if search_team:
        orders = orders.filter(production_team_id=search_team)

    # 🌟 3. แยกกลุ่มข้อมูล 🌟
    active_qs = orders.filter(is_closed=False)
    closed_qs = orders.filter(is_closed=True)

    # 🌟 4. ระบบแบ่งหน้า (Pagination) กลุ่ม Active 🌟
    active_paginator = Paginator(active_qs, 10) # 10 รายการต่อหน้า
    active_page_num = request.GET.get('active_page', 1)
    active_orders = active_paginator.get_page(active_page_num)

    # 🌟 5. ระบบแบ่งหน้า (Pagination) กลุ่ม Closed 🌟
    closed_paginator = Paginator(closed_qs, 10) # 10 รายการต่อหน้า
    closed_page_num = request.GET.get('closed_page', 1)
    closed_orders = closed_paginator.get_page(closed_page_num)

    # 🌟 6. สร้าง QueryString ไว้แปะตอนเปลี่ยนหน้า (เพื่อให้การค้นหาไม่หลุด) 🌟
    url_params = request.GET.copy()
    if 'active_page' in url_params: del url_params['active_page']
    if 'closed_page' in url_params: del url_params['closed_page']
    filter_string = url_params.urlencode()

    # ดึงข้อมูลตัวเลือก Dropdown
    prod_statuses = ProductionStatus.objects.all().order_by('name')
    prod_teams = ProductionTeam.objects.all().order_by('name')
    deliv_statuses = DeliveryStatus.objects.all().order_by('name')
    transporters = Transporter.objects.all().order_by('name')
    salespersons = Salesperson.objects.all().order_by('name')
    
    return render(request, 'manufacturing/production_list.html', {
        'active_orders': active_orders,
        'closed_orders': closed_orders,
        'prod_statuses': prod_statuses,
        'prod_teams': prod_teams,
        'deliv_statuses': deliv_statuses,
        'transporters': transporters,
        'salespersons': salespersons,
        # ส่งค่ากลับไปให้หน้าเว็บ
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_salesperson': search_salesperson,
        'search_team': search_team,
        'filter_string': filter_string, # ส่ง QueryString ไปใช้ใน Template
    })

# --- (ฟังก์ชันอื่นๆ ด้านล่าง คงไว้เหมือนเดิมทั้งหมดครับ) ---
@login_required
def production_create(request):
    boms = BOM.objects.select_related('product').all()
    fg_with_bom = [bom.product for bom in boms]
    
    branches = Branch.objects.all().order_by('name')
    salespersons = Salesperson.objects.select_related('branch').all().order_by('name')

    if request.method == 'POST':
        product_id = request.POST.get('product')
        note = request.POST.get('note', '')
        
        start_date = request.POST.get('start_date')
        delivery_date = request.POST.get('delivery_date')
        branch_id = request.POST.get('branch')
        salesperson_id = request.POST.get('salesperson')
        customer_name = request.POST.get('customer_name', '')

        if product_id:
            product = get_object_or_404(Product, id=product_id)
            
            order = ProductionOrder(
                product=product,
                quantity=1, 
                status='PLANNED',
                note=note,
                customer_name=customer_name,
                responsible_person=getattr(request.user, 'employee', None)
            )
            
            if start_date: order.start_date = start_date
            if delivery_date: order.delivery_date = delivery_date
            if branch_id: order.branch_id = branch_id
            if salesperson_id: order.salesperson_id = salesperson_id
            
            order.save()

            messages.success(request, f"✅ สร้างใบสั่งผลิต {order.code} สำเร็จ! (สำหรับบ้าน 1 หลัง)")
            return redirect('production_list')
        else:
            messages.error(request, "❌ กรุณาเลือกแบบบ้านที่ต้องการผลิต")

    return render(request, 'manufacturing/production_form.html', {
        'fg_with_bom': fg_with_bom,
        'branches': branches,
        'salespersons': salespersons
    })

@login_required
@transaction.atomic 
def production_process(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status == 'COMPLETED':
        messages.warning(request, "⚠️ รายการนี้ผลิตเสร็จและรับเข้าคลังไปแล้ว!")
        return redirect('production_list')
    bom = BOM.objects.filter(product=order.product).first()
    if not bom:
        messages.error(request, "❌ ไม่พบสูตรผลิตสำหรับสินค้านี้")
        return redirect('production_list')
    shortage = []
    for item in bom.items.all():
        required_qty = float(item.quantity) * order.quantity
        if float(item.raw_material.stock_qty) < required_qty:
            shortage.append(f"{item.raw_material.name} (ขาด {required_qty - float(item.raw_material.stock_qty):.2f})")
    if shortage:
        err_msg = " / ".join(shortage)
        messages.error(request, f"❌ ไม่สามารถผลิตได้! วัตถุดิบไม่พอ: {err_msg}")
        return redirect('production_list')
    doc_out = InventoryDoc.objects.create(doc_type='GI', reference=f"เบิกผลิต {order.code}", description=f"เบิกวัตถุดิบผลิต {order.product.name} จำนวน {order.quantity}", created_by=request.user)
    for item in bom.items.all():
        StockMovement.objects.create(doc=doc_out, product=item.raw_material, quantity=float(item.quantity) * order.quantity, movement_type='OUT', created_by=request.user)
    doc_in = InventoryDoc.objects.create(doc_type='GR', reference=f"รับจาก {order.code}", description=f"รับสินค้าสำเร็จรูปจากการผลิต {order.code}", created_by=request.user)
    StockMovement.objects.create(doc=doc_in, product=order.product, quantity=order.quantity, movement_type='IN', created_by=request.user)
    order.status = 'COMPLETED'
    order.finish_date = timezone.now().date()
    order.save()
    messages.success(request, f"🎉 ตัดสต็อกสำเร็จ! หักวัตถุดิบและนำ {order.product.name} ({order.quantity} ชิ้น) เข้าคลังเรียบร้อยแล้ว!")
    return redirect('production_list')

@login_required
def ppo_prepare(request):
    available_jobs = ProductionOrder.objects.filter(status__in=['PLANNED', 'IN_PROGRESS'], is_materials_ordered=False).order_by('code')
    ppo_code = ""
    materials_by_supplier = {}
    selected_job_ids = []
    if request.method == 'POST':
        selected_job_ids = request.POST.getlist('job_ids')
        if selected_job_ids:
            ppo = PurchasePreparation.objects.create(created_by=getattr(request.user, 'employee', None))
            jobs = ProductionOrder.objects.filter(id__in=selected_job_ids)
            ppo.production_orders.set(jobs)
            ppo_code = ppo.code
            for job in jobs:
                bom = BOM.objects.filter(product=job.product).first()
                if bom:
                    for item in bom.items.all():
                        total_needed = float(item.quantity)
                        supplier = item.raw_material.supplier
                        sup_id = supplier.id if supplier else "none"
                        sup_name = supplier.name if supplier else "ไม่ได้ระบุร้านค้า"
                        mat_id = item.raw_material.id
                        if sup_id not in materials_by_supplier: materials_by_supplier[sup_id] = {'name': sup_name, 'items': {}}
                        if mat_id not in materials_by_supplier[sup_id]['items']:
                            materials_by_supplier[sup_id]['items'][mat_id] = {'product_id': item.raw_material.id, 'product_name': item.raw_material.name, 'product_code': item.raw_material.code, 'qty': 0, 'cost': float(item.raw_material.cost_price), 'total': 0}
                        materials_by_supplier[sup_id]['items'][mat_id]['qty'] += total_needed
                        materials_by_supplier[sup_id]['items'][mat_id]['total'] = materials_by_supplier[sup_id]['items'][mat_id]['qty'] * materials_by_supplier[sup_id]['items'][mat_id]['cost']
            for sup_id in materials_by_supplier: materials_by_supplier[sup_id]['items'] = list(materials_by_supplier[sup_id]['items'].values())
            jobs.update(is_materials_ordered=True)
        else: messages.warning(request, "⚠️ กรุณาติ๊กเลือกอย่างน้อย 1 ใบสั่งผลิต (JOB) เพื่อคำนวณวัตถุดิบ")
    return render(request, 'manufacturing/ppo_prepare.html', {'available_jobs': available_jobs, 'ppo_code': ppo_code, 'materials_by_supplier': materials_by_supplier, 'selected_job_ids': [int(i) for i in selected_job_ids]})

@login_required
def production_detail(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    return render(request, 'manufacturing/production_detail.html', {'order': order})

@login_required
def generate_pos_from_production(request, pk):
    messages.info(request, "ฟังก์ชันนี้กำลังอยู่ระหว่างการพัฒนาเพิ่มเติม")
    return redirect('ppo_prepare')

@login_required
def production_print(request, po_id):
    po = get_object_or_404(ProductionOrder, id=po_id)
    bom = BOM.objects.filter(product=po.product).first()
    company = CompanyInfo.objects.first()
    return render(request, 'manufacturing/production_print.html', {'po': po, 'bom': bom, 'company': company})

@login_required
def bom_list(request):
    boms = BOM.objects.select_related('product').annotate(item_count=Count('items')).order_by('-id')
    return render(request, 'manufacturing/bom_list.html', {'boms': boms})

@login_required
def bom_create(request):
    if request.method == 'POST':
        form = BOMForm(request.POST)
        formset = BOMItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            bom = form.save()
            formset.instance = bom
            formset.save()
            messages.success(request, f"✅ สร้างสูตรผลิตสำหรับ {bom.product.name} เรียบร้อยแล้ว!")
            return redirect('bom_detail', pk=bom.pk)
    else:
        form = BOMForm()
        formset = BOMItemFormSet()
    return render(request, 'manufacturing/bom_form.html', {'form': form, 'formset': formset, 'title': 'สร้างสูตรผลิตใหม่ (New BOM)'})

@login_required
def bom_detail(request, pk):
    bom = get_object_or_404(BOM, pk=pk)
    items = bom.items.all()
    total_cost = sum([float(item.quantity) * float(item.raw_material.cost_price) for item in items])
    return render(request, 'manufacturing/bom_detail.html', {'bom': bom, 'items': items, 'total_cost': total_cost})

@login_required
def bom_edit(request, pk):
    bom = get_object_or_404(BOM, pk=pk)
    if request.method == 'POST':
        form = BOMForm(request.POST, instance=bom)
        formset = BOMItemFormSet(request.POST, instance=bom)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ แก้ไขสูตรผลิต {bom.product.name} เรียบร้อยแล้ว!")
            return redirect('bom_detail', pk=bom.pk)
    else:
        form = BOMForm(instance=bom)
        formset = BOMItemFormSet(instance=bom)
    return render(request, 'manufacturing/bom_form.html', {'form': form, 'formset': formset, 'title': f'แก้ไขสูตรผลิต: {bom.product.code}'})

# ==========================================
# 🌟 AJAX Views และ อัปเดตกระดานงานผลิต 🌟
# ==========================================
@login_required
def update_production_board(request, pk):
    if request.method == 'POST':
        order = get_object_or_404(ProductionOrder, pk=pk)
        
        # รับค่าจาก Popup Modal มาอัปเดตบิล
        order.production_status_id = request.POST.get('production_status') or None
        order.production_team_id = request.POST.get('production_team') or None
        order.delivery_status_id = request.POST.get('delivery_status') or None
        order.transporter_id = request.POST.get('transporter') or None
        
        # รับค่า สวิตช์ปิดจ๊อบ
        is_closed = request.POST.get('is_closed')
        if is_closed == 'on':
            order.is_closed = True
            messages.success(request, f"✅ ปิดจ๊อบ {order.code} เรียบร้อยแล้ว! (ย้ายไปแท็บประวัติ)")
        else:
            order.is_closed = False
            messages.success(request, f"✅ อัปเดตสถานะงาน {order.code} เรียบร้อยแล้ว!")
            
        order.save()
        
    return redirect('production_list')

@login_required
def ajax_add_branch(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        if name:
            obj, created = Branch.objects.get_or_create(name=name)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
    return JsonResponse({'success': False})

@login_required
def ajax_add_salesperson(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        branch_id = data.get('branch_id')
        if name and branch_id:
            obj, created = Salesperson.objects.get_or_create(name=name, branch_id=branch_id)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name, 'branch_id': obj.branch.id})
    return JsonResponse({'success': False})

@login_required
def ajax_add_prod_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        if name:
            obj, _ = ProductionStatus.objects.get_or_create(name=name)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
    return JsonResponse({'success': False})

@login_required
def ajax_add_prod_team(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        if name:
            obj, _ = ProductionTeam.objects.get_or_create(name=name)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
    return JsonResponse({'success': False})

@login_required
def ajax_add_delivery_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        if name:
            obj, _ = DeliveryStatus.objects.get_or_create(name=name)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
    return JsonResponse({'success': False})

@login_required
def ajax_add_transporter(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        if name:
            obj, _ = Transporter.objects.get_or_create(name=name)
            return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
    return JsonResponse({'success': False})