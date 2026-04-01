from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Max, Count, Q
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
import datetime
import calendar
import json

from .models import ProductionOrder, ProductionOrderMaterial, BOM, Branch, Salesperson, ProductionStatus, ProductionTeam, DeliveryStatus, Transporter
from master_data.models import CompanyInfo
from inventory.models import Product, InventoryDoc, StockMovement
from purchasing.models import PurchaseOrder, PurchaseOrderItem, PurchasePreparation
from .forms import BOMForm, BOMItemFormSet

# ==========================================
# 🌟 ระบบใบสั่งผลิต (Production Order) 🌟
# ==========================================
@login_required
def production_list(request):
    # 🌟 [UPDATE 2026] ปรับค่าเริ่มต้นให้วันที่ว่าง เพื่อโชว์งานค้างทั้งหมด 🌟
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    search_q = request.GET.get('q', '')
    search_salesperson = request.GET.get('salesperson', '')
    search_team = request.GET.get('team', '')
    search_status = request.GET.get('status', '') # 🌟 ตัวรับค่าจาก Dropdown สถานะระบบ

    orders = ProductionOrder.objects.select_related(
        'product', 'quotation_ref', 'salesperson', 
        'production_team', 'delivery_status', 'transporter'
    ).prefetch_related('completed_departments').all().order_by('-id')

    # 🔍 ระบบกรองข้อมูล
    if start_date:
        orders = orders.filter(start_date__gte=start_date)
    if end_date:
        orders = orders.filter(start_date__lte=end_date)
    
    if search_status:
        orders = orders.filter(status=search_status)

    if search_q:
        orders = orders.filter(
            Q(code__icontains=search_q) |
            Q(customer_name__icontains=search_q) |
            Q(quotation_ref__code__icontains=search_q)
        )
        
    if search_salesperson:
        orders = orders.filter(salesperson_id=search_salesperson)
    if search_team:
        orders = orders.filter(production_team_id=search_team)

    active_qs = orders.filter(is_closed=False)
    closed_qs = orders.filter(is_closed=True)

    active_paginator = Paginator(active_qs, 10)
    active_page_num = request.GET.get('active_page', 1)
    active_orders = active_paginator.get_page(active_page_num)

    closed_paginator = Paginator(closed_qs, 10)
    closed_page_num = request.GET.get('closed_page', 1)
    closed_orders = closed_paginator.get_page(closed_page_num)

    url_params = request.GET.copy()
    if 'active_page' in url_params: del url_params['active_page']
    if 'closed_page' in url_params: del url_params['closed_page']
    filter_string = url_params.urlencode()

    prod_statuses = ProductionStatus.objects.all().order_by('sequence', 'id')
    prod_teams = ProductionTeam.objects.all().order_by('name')
    deliv_statuses = DeliveryStatus.objects.all().order_by('name')
    transporters = Transporter.objects.all().order_by('name')
    salespersons = Salesperson.objects.all().order_by('name')
    total_departments_count = prod_statuses.count()

    # ดึง Choices สถานะระบบจาก Model มาทำตัวกรอง
    system_status_choices = ProductionOrder.STATUS_CHOICES

    can_add_master_data = False
    if request.user.is_superuser:
        can_add_master_data = True
    else:
        current_emp = getattr(request.user, 'employee', None)
        is_manager = False
        is_planner = False
        
        user_groups = list(request.user.groups.values_list('name', flat=True))
        if any('Manager' in g for g in user_groups): is_manager = True
        if any('Planner' in g or 'Production' in g for g in user_groups): is_planner = True
        
        if current_emp:
            rank = current_emp.business_rank.lower() if current_emp.business_rank else ""
            job_title = current_emp.position.title.lower() if current_emp.position else ""
            dept_name = current_emp.department.name if current_emp.department else ""
            
            if rank in ['manager', 'director'] or 'manager' in job_title:
                is_manager = True
            if 'วางแผน' in dept_name or 'ผลิต' in dept_name:
                is_planner = True
                
        if is_manager and is_planner:
            can_add_master_data = True

    return render(request, 'manufacturing/production_list.html', {
        'active_orders': active_orders,
        'closed_orders': closed_orders,
        'prod_statuses': prod_statuses,
        'prod_teams': prod_teams,
        'deliv_statuses': deliv_statuses,
        'transporters': transporters,
        'salespersons': salespersons,
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_salesperson': search_salesperson,
        'search_team': search_team,
        'search_status': search_status,
        'system_status_choices': system_status_choices,
        'filter_string': filter_string,
        'can_add_master_data': can_add_master_data,
        'total_departments_count': total_departments_count,
    })

@login_required
def planner_board(request):
    orders = ProductionOrder.objects.filter(status='PLANNED', is_closed=False).order_by('-id')
    return render(request, 'manufacturing/planner_board.html', {'orders': orders})

@login_required
def inventory_board(request):
    orders = ProductionOrder.objects.filter(status='WAITING_INVENTORY', is_closed=False).order_by('status', '-id')
    
    for order in orders:
        shortage = []
        for item in order.materials.all():
            required_qty = float(item.quantity)
            stock_qty = float(item.raw_material.stock_qty)
            if stock_qty < required_qty:
                shortage.append(f"{item.raw_material.name} (ขาดอีก {required_qty - stock_qty:.2f})")
        
        order.has_shortage = len(shortage) > 0
        order.shortage_list = ", ".join(shortage)

    return render(request, 'manufacturing/inventory_board.html', {'orders': orders})

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
            messages.success(request, f"✅ สร้างใบสั่งผลิต {order.code} สำเร็จ! (สถานะ: รอตรวจสอบแบบแปลน)")
            return redirect('production_list')
        else:
            messages.error(request, "❌ กรุณาเลือกแบบบ้านที่ต้องการผลิต")

    return render(request, 'manufacturing/production_form.html', {
        'fg_with_bom': fg_with_bom,
        'branches': branches,
        'salespersons': salespersons
    })

@login_required
def start_production(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if not order.materials.exists():
        messages.warning(request, "⚠️ กรุณาดึงรายการวัตถุดิบ (BOM) ก่อนกดยืนยันแผนการผลิต!")
        return redirect('production_detail', pk=order.pk)

    order.status = 'WAITING_MATERIALS'
    order.save()
    messages.success(request, f"🚀 ยืนยันแผนงาน {order.code} แล้ว! งานถูกส่งไปที่ฝ่ายจัดซื้อ")
    return redirect('production_list')

@login_required
def ppo_prepare(request):
    available_jobs = ProductionOrder.objects.filter(status='WAITING_MATERIALS', is_materials_ordered=False).order_by('code')
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
            
            jobs.update(is_materials_ordered=True, status='WAITING_INVENTORY')
        else: 
            messages.warning(request, "⚠️ กรุณาติ๊กเลือกอย่างน้อย 1 ใบสั่งผลิต (JOB) เพื่อคำนวณวัตถุดิบ")
    return render(request, 'manufacturing/ppo_prepare.html', {'available_jobs': available_jobs, 'ppo_code': ppo_code, 'materials_by_supplier': materials_by_supplier, 'selected_job_ids': [int(i) for i in selected_job_ids]})

@login_required
@transaction.atomic
def materials_ready(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    job_materials = order.materials.all()
    if not job_materials:
        messages.error(request, "❌ ไม่พบรายการวัตถุดิบในใบสั่งผลิตนี้")
        return redirect('inventory_board')

    shortage = []
    for item in job_materials:
        required_qty = float(item.quantity)
        if float(item.raw_material.stock_qty) < required_qty:
            shortage.append(f"{item.raw_material.name} (ขาด {required_qty - float(item.raw_material.stock_qty):.2f})")
    
    if shortage:
        err_msg = " / ".join(shortage)
        messages.error(request, f"❌ ไม่สามารถตัดสต็อกได้! วัตถุดิบในคลังไม่พอ: {err_msg}")
        return redirect('inventory_board')
    
    doc_out = InventoryDoc.objects.create(doc_type='GI', reference=f"เบิกผลิต {order.code}", description=f"เบิกวัตถุดิบเตรียมผลิต {order.product.name}", created_by=request.user)
    for item in job_materials:
        StockMovement.objects.create(doc=doc_out, product=item.raw_material, quantity=float(item.quantity), movement_type='OUT', created_by=request.user)
        
        item.raw_material.stock_qty = float(item.raw_material.stock_qty) - float(item.quantity)
        
        item.raw_material.save()
    
    order.status = 'IN_PROGRESS'
    order.save()
    messages.success(request, f"✅ ตัดสต็อกสำเร็จ! สถานะเปลี่ยนเป็น 'งานอยู่ระหว่างผลิต' แล้ว")
    return redirect('inventory_board')

@login_required
def start_actual_production(request, pk):
    return redirect('production_list')

@login_required
@transaction.atomic
def production_process(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status == 'COMPLETED':
        messages.warning(request, "⚠️ รายการนี้ผลิตเสร็จและรับเข้าคลังไปแล้ว!")
        return redirect('production_list')
    
    alloc_code = f"{order.product.code}-{order.code}"
    alloc_name = f"{order.product.name} [{order.code}]"
    if order.customer_name:
        alloc_name += f" (ลค. {order.customer_name})"
        
    allocated_product, created = Product.objects.get_or_create(
        code=alloc_code,
        defaults={
            'name': alloc_name[:255],
            'category': order.product.category,
            'product_type': 'FG',
            'sell_price': order.product.sell_price,
            'cost_price': order.product.cost_price,
            'min_level': 0,
            'stock_qty': 0,
            'is_active': True,
        }
    )

    doc_in = InventoryDoc.objects.create(doc_type='GR', reference=f"รับจาก {order.code}", description=f"รับสินค้าสำเร็จรูปจากการผลิต {order.code}", created_by=request.user)
    
    StockMovement.objects.create(doc=doc_in, product=allocated_product, quantity=order.quantity, movement_type='IN', created_by=request.user)
    
    allocated_product.stock_qty += order.quantity
    allocated_product.save()

    order.status = 'COMPLETED'
    order.finish_date = timezone.now().date()
    order.save()
    
    messages.success(request, f"🎉 สำเร็จ! รับ {allocated_product.name} ({order.quantity} หลัง) เข้าคลังเรียบร้อยแล้ว!")
    return redirect('production_list')

@login_required
def production_detail(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    materials = order.materials.all() 
    has_bom = BOM.objects.filter(product=order.product).exists() 
    raw_materials = Product.objects.filter(product_type='RM', is_active=True).order_by('code')
    
    return render(request, 'manufacturing/production_detail.html', {
        'order': order,
        'materials': materials,
        'has_bom': has_bom,
        'raw_materials': raw_materials
    })

@login_required
def print_bom(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    materials = order.materials.all()
    company = CompanyInfo.objects.first()
    return render(request, 'manufacturing/print_bom.html', {'order': order, 'materials': materials, 'company': company})

@login_required
def upload_blueprint(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if request.method == 'POST' and 'blueprint_file' in request.FILES:
        order.blueprint_file = request.FILES['blueprint_file']
        order.save()
        messages.success(request, f"📎 แนบไฟล์แบบแปลน (Blueprint) สำหรับ {order.code} เรียบร้อยแล้ว")
    return redirect('production_detail', pk=order.pk)

@login_required
def load_standard_bom(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    
    if order.materials.exists():
        messages.warning(request, "⚠️ มีการดึงรายการสูตรผลิตในใบสั่งผลิตนี้ไปแล้ว")
        return redirect('production_detail', pk=order.pk)
        
    bom = BOM.objects.filter(product=order.product).first()
    if not bom:
        messages.error(request, "❌ ไม่พบสูตรผลิตมาตรฐาน (BOM) สำหรับสินค้ารุ่นนี้")
        return redirect('production_detail', pk=order.pk)
        
    for item in bom.items.all():
        ProductionOrderMaterial.objects.create(
            production_order=order,
            raw_material=item.raw_material,
            quantity=item.quantity * order.quantity,
            is_additional=False
        )
    messages.success(request, "📋 ดึงรายการวัตถุดิบจากสูตรมาตรฐานเรียบร้อยแล้ว!")
    return redirect('production_detail', pk=order.pk)

@login_required
def add_additional_material(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if request.method == 'POST':
        product_id = request.POST.get('raw_material')
        qty = float(request.POST.get('quantity', 0))
        
        if product_id and qty > 0:
            rm = get_object_or_404(Product, pk=product_id)
            ProductionOrderMaterial.objects.create(
                production_order=order,
                raw_material=rm,
                quantity=qty,
                is_additional=True 
            )
            messages.success(request, f"➕ เพิ่มวัตถุดิบส่วนเพิ่ม: {rm.name} จำนวน {qty} ลงในบิลเรียบร้อยแล้ว")
        else:
             messages.error(request, "❌ กรุณาเลือกวัตถุดิบและใส่จำนวนให้ถูกต้อง")
    return redirect('production_detail', pk=order.pk)

@login_required
def delete_production_material(request, pk):
    mat = get_object_or_404(ProductionOrderMaterial, pk=pk)
    order_id = mat.production_order.id
    if mat.production_order.status != 'COMPLETED':
        mat.delete()
        messages.success(request, "🗑️ ลบรายการวัตถุดิบออกจากบิลผลิตเรียบร้อยแล้ว")
    else:
        messages.error(request, "❌ ไม่สามารถลบได้เนื่องจากใบสั่งผลิตนี้ดำเนินการเสร็จสิ้นแล้ว")
    return redirect('production_detail', pk=order_id)

@login_required
def blueprint_viewer(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    return render(request, 'manufacturing/blueprint_viewer.html', {'order': order})

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

@login_required
def update_production_board(request, pk):
    if request.method == 'POST':
        order = get_object_or_404(ProductionOrder, pk=pk)

        selected_depts = request.POST.getlist('completed_departments')
        order.completed_departments.set(selected_depts)

        order.production_team_id = request.POST.get('production_team') or None
        order.delivery_status_id = request.POST.get('delivery_status') or None
        order.transporter_id = request.POST.get('transporter') or None

        is_closed = request.POST.get('is_closed')
        if is_closed == 'on':
            order.is_closed = True
            messages.success(request, f"✅ ปิดจ๊อบ {order.code} เรียบร้อยแล้ว! (ย้ายไปแท็บประวัติ)")
        else:
            order.is_closed = False
            messages.success(request, f"✅ อัปเดตความคืบหน้า {order.code} เรียบร้อยแล้ว!")

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
            obj, _ = ProductionStatus.objects.get_or_create(name=name, defaults={'sequence': 99})
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

@login_required
def ajax_get_fg_by_category(request):
    category_id = request.GET.get('category_id')
    products = Product.objects.filter(product_type='FG', is_active=True).exclude(code__contains='-JOB')
    if category_id:
        products = products.filter(category_id=category_id)
    product_list = list(products.values('id', 'name', 'code'))
    return JsonResponse({'products': product_list})