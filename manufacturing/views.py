from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Max, Count, Q, Sum, F, FloatField
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
import datetime
import calendar
import json
import pandas as pd

from .models import ProductionOrder, ProductionOrderMaterial, BOM, BOMItem, Branch, MfgBranch, Salesperson, ProductionStatus, ProductionTeam, DeliveryStatus, Transporter, QCInspectionLog
from master_data.models import CompanyInfo
from inventory.models import Product, InventoryDoc, StockMovement
from purchasing.models import PurchaseOrder, PurchaseOrderItem, PurchasePreparation
from .forms import BOMForm, BOMItemFormSet

# ==========================================
# 🌟 ระบบใบสั่งผลิต (Production Order) 🌟
# ==========================================
@login_required
def production_list(request):
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    search_q = request.GET.get('q', '')
    search_salesperson = request.GET.get('salesperson', '')
    search_team = request.GET.get('team', '')
    search_status = request.GET.get('status', '')
    search_branch = request.GET.get('branch', '')

    orders = ProductionOrder.objects.select_related(
        'product', 'quotation_ref', 'salesperson',
        'production_team', 'delivery_status', 'transporter', 'branch'
    ).prefetch_related('completed_departments').all().order_by('-id')

    if start_date:
        orders = orders.filter(start_date__gte=start_date)
    if end_date:
        orders = orders.filter(start_date__lte=end_date)
    if search_status:
        orders = orders.filter(status=search_status)
    if search_branch:
        orders = orders.filter(branch_id=search_branch)
    if search_q:
        orders = orders.filter(
            Q(code__icontains=search_q) | Q(customer_name__icontains=search_q) | Q(quotation_ref__code__icontains=search_q)
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

    branches = MfgBranch.objects.all().order_by('name')
    prod_statuses = ProductionStatus.objects.all().order_by('sequence', 'id')
    prod_teams = ProductionTeam.objects.all().order_by('name')
    deliv_statuses = DeliveryStatus.objects.all().order_by('name')
    transporters = Transporter.objects.all().order_by('name')
    salespersons = Salesperson.objects.all().order_by('name')
    total_departments_count = prod_statuses.count()
    system_status_choices = ProductionOrder.STATUS_CHOICES

    can_add_master_data = False
    is_sales = False 

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

            if 'ขาย' in dept_name or 'sales' in dept_name.lower():
                 is_sales = True

        if is_manager and is_planner:
            can_add_master_data = True

    return render(request, 'manufacturing/production_list.html', {
        'active_orders': active_orders,
        'closed_orders': closed_orders,
        'branches': branches,
        'prod_statuses': prod_statuses,
        'prod_teams': prod_teams,
        'deliv_statuses': deliv_statuses,
        'transporters': transporters,
        'salespersons': salespersons,
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_branch': search_branch,
        'search_salesperson': search_salesperson,
        'search_team': search_team,
        'search_status': search_status,
        'system_status_choices': system_status_choices,
        'filter_string': filter_string,
        'can_add_master_data': can_add_master_data,
        'is_sales': is_sales,
        'total_departments_count': total_departments_count,
    })

@login_required
def planner_board(request):
    today = timezone.now().date()
    default_start = today - datetime.timedelta(days=30)
    # 🌟 [FIXED] ตั้งค่าเริ่มต้นให้ดึงล่วงหน้า 30 วัน 🌟
    default_end = today + datetime.timedelta(days=30)

    start_date = request.GET.get('start_date', default_start.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', default_end.strftime('%Y-%m-%d'))
    
    search_q = request.GET.get('q', '')
    search_branch = request.GET.get('branch', '')
    search_team = request.GET.get('team', '')
    search_salesperson = request.GET.get('salesperson', '')

    orders = ProductionOrder.objects.select_related(
        'product', 'branch', 'production_team', 'salesperson', 'salesperson__branch', 'quotation_ref'
    ).all().order_by('-id')

    if start_date: orders = orders.filter(start_date__gte=start_date)
    if end_date: orders = orders.filter(start_date__lte=end_date)
    if search_q:
        orders = orders.filter(Q(code__icontains=search_q) | Q(customer_name__icontains=search_q) | Q(product__name__icontains=search_q))
    if search_branch: orders = orders.filter(branch_id=search_branch)
    if search_team: orders = orders.filter(production_team_id=search_team)
    if search_salesperson: orders = orders.filter(salesperson_id=search_salesperson)

    branches = MfgBranch.objects.all().order_by('name')
    teams = ProductionTeam.objects.all().order_by('name')
    salespersons = Salesperson.objects.select_related('branch').all().order_by('name')

    prod_statuses = ProductionStatus.objects.all().order_by('sequence', 'id')
    deliv_statuses = DeliveryStatus.objects.all().order_by('name')
    transporters = Transporter.objects.all().order_by('name')

    return render(request, 'manufacturing/planner_board.html', {
        'orders': orders,
        'branches': branches,
        'teams': teams,
        'salespersons': salespersons,
        'prod_statuses': prod_statuses,
        'deliv_statuses': deliv_statuses,
        'transporters': transporters,
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_branch': search_branch,
        'search_team': search_team,
        'search_salesperson': search_salesperson,
    })

@login_required
def inventory_board(request):
    orders = ProductionOrder.objects.filter(status='WAITING_INVENTORY', is_closed=False).order_by('status', '-id')
    virtual_stock = {}

    for order in orders:
        shortage = []
        for item in order.materials.all():
            mat_id = item.raw_material.id
            required_qty = Decimal(str(item.quantity))

            if mat_id not in virtual_stock:
                virtual_stock[mat_id] = max(Decimal('0'), item.raw_material.stock_qty or Decimal('0'))

            if virtual_stock[mat_id] < required_qty:
                missing = required_qty - virtual_stock[mat_id]
                shortage.append(f"{item.raw_material.name} (ขาดอีก {missing:.2f})")
                virtual_stock[mat_id] = Decimal('0')
            else:
                virtual_stock[mat_id] -= required_qty

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
                status='NEW_JOB',
                note=note,
                customer_name=customer_name,
                responsible_person=getattr(request.user, 'employee', None)
            )

            if start_date: order.start_date = start_date
            if delivery_date: order.delivery_date = delivery_date
            if salesperson_id: order.salesperson_id = salesperson_id

            order.save()
            messages.success(request, f"✅ สร้างใบสั่งผลิต {order.code} สำเร็จ! งานถูกส่งไปยังคอลัมน์รอจ่ายงาน (W1)")
            return redirect('planner_board')
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
                        total_needed = Decimal(str(item.quantity))
                        supplier = item.raw_material.supplier
                        sup_id = supplier.id if supplier else "none"
                        sup_name = supplier.name if supplier else "ไม่ได้ระบุร้านค้า"
                        mat_id = item.raw_material.id
                        if sup_id not in materials_by_supplier: materials_by_supplier[sup_id] = {'name': sup_name, 'items': {}}

                        if mat_id not in materials_by_supplier[sup_id]['items']:
                            materials_by_supplier[sup_id]['items'][mat_id] = {
                                'product_id': item.raw_material.id,
                                'product_name': item.raw_material.name,
                                'product_code': item.raw_material.code,
                                'qty': Decimal('0'),
                                'cost': item.raw_material.cost_price or Decimal('0'),
                                'total': Decimal('0')
                            }
                        materials_by_supplier[sup_id]['items'][mat_id]['qty'] += total_needed
                        materials_by_supplier[sup_id]['items'][mat_id]['total'] = materials_by_supplier[sup_id]['items'][mat_id]['qty'] * materials_by_supplier[sup_id]['items'][mat_id]['cost']

            for sup_id in materials_by_supplier:
                items_list = []
                for v in materials_by_supplier[sup_id]['items'].values():
                    v['qty'] = float(v['qty'])
                    v['cost'] = float(v['cost'])
                    v['total'] = float(v['total'])
                    items_list.append(v)
                materials_by_supplier[sup_id]['items'] = items_list

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
        required_qty = Decimal(str(item.quantity))
        actual_stock = max(Decimal('0'), item.raw_material.stock_qty or Decimal('0'))
        if actual_stock < required_qty:
            shortage.append(f"{item.raw_material.name} (ขาด {required_qty - actual_stock:.2f})")

    if shortage:
        err_msg = " / ".join(shortage)
        messages.error(request, f"❌ ไม่สามารถตัดสต็อกได้! วัตถุดิบในคลังไม่พอ: {err_msg}")
        return redirect('inventory_board')

    doc_out = InventoryDoc.objects.create(doc_type='GI', reference=f"เบิกผลิต {order.code}", description=f"เบิกวัตถุดิบเตรียมผลิต {order.product.name}", created_by=request.user)
    for item in job_materials:
        StockMovement.objects.create(doc=doc_out, product=item.raw_material, quantity=Decimal(str(item.quantity)), movement_type='OUT', created_by=request.user)
        item.raw_material.stock_qty = (item.raw_material.stock_qty or Decimal('0')) - Decimal(str(item.quantity))
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
    if order.customer_name: alloc_name += f" (ลค. {order.customer_name})"

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
    StockMovement.objects.create(doc=doc_in, product=allocated_product, quantity=Decimal(str(order.quantity)), movement_type='IN', created_by=request.user)

    allocated_product.stock_qty = (allocated_product.stock_qty or Decimal('0')) + Decimal(str(order.quantity))
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
        try:
            qty = Decimal(request.POST.get('quantity', '0'))
        except:
            qty = Decimal('0')

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
    boms = BOM.objects.select_related('product').annotate(
        item_count=Count('items', distinct=True),
        total_rm_cost=Sum(
            F('items__quantity') * F('items__raw_material__cost_price'),
            output_field=FloatField()
        )
    ).order_by('-id')
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
    items = bom.items.select_related('raw_material', 'raw_material__supplier').all()

    total_cost = Decimal('0')
    for item in items:
        item.calculated_total_cost = Decimal(str(item.quantity)) * (item.raw_material.cost_price or Decimal('0'))
        total_cost += item.calculated_total_cost

    return render(request, 'manufacturing/bom_detail.html', {'bom': bom, 'items': items, 'total_cost': total_cost})

@login_required
def bom_edit(request, pk):
    bom = get_object_or_404(BOM.objects.prefetch_related('items'), pk=pk)

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
def print_master_bom(request, pk):
    bom = get_object_or_404(BOM, pk=pk)
    items = bom.items.select_related('raw_material', 'raw_material__supplier').all()

    total_cost = Decimal('0')
    for item in items:
        item.calculated_total_cost = Decimal(str(item.quantity)) * (item.raw_material.cost_price or Decimal('0'))
        total_cost += item.calculated_total_cost

    company = CompanyInfo.objects.first()
    return render(request, 'manufacturing/print_master_bom.html', {
        'bom': bom,
        'items': items,
        'total_cost': total_cost,
        'company': company
    })

@login_required
def update_production_board(request, pk):
    if request.method == 'POST':
        order = get_object_or_404(ProductionOrder, pk=pk)
        action = request.POST.get('action')

        if 'completed_departments' in request.POST:
            selected_depts = request.POST.getlist('completed_departments')
            order.completed_departments.set(selected_depts)
        elif action in ['update_progress', 'qc_complete_and_receive']:
            order.completed_departments.clear()

        if 'production_team' in request.POST:
            order.production_team_id = request.POST.get('production_team') or None
        if 'delivery_status' in request.POST:
            order.delivery_status_id = request.POST.get('delivery_status') or None
        if 'transporter' in request.POST:
            order.transporter_id = request.POST.get('transporter') or None
        if 'branch' in request.POST:
            order.branch_id = request.POST.get('branch') or None

        if action == 'dispatch' and order.status == 'NEW_JOB':
            order.status = 'PLANNED'
            messages.success(request, f"✅ จ่ายงาน {order.code} ไปยัง {order.branch.name if order.branch else 'ไม่ระบุโรงงาน'} เรียบร้อยแล้ว! (สถานะ: ตรวจแบบแปลน)")

        elif action in ['update_progress', 'qc_complete_and_receive']:
            # 🌟 รับค่าติ๊ก Checklist QC 6 ข้อ
            order.qc_paint = request.POST.get('qc_paint') == 'on'
            order.qc_internal = request.POST.get('qc_internal') == 'on'
            order.qc_external = request.POST.get('qc_external') == 'on'
            order.qc_electrical = request.POST.get('qc_electrical') == 'on'
            order.qc_plumbing = request.POST.get('qc_plumbing') == 'on'
            order.qc_aircon = request.POST.get('qc_aircon') == 'on'

            # 🌟 ย้ายลอจิกการรับเข้าคลังมาไว้ที่ปุ่มนี้
            if action == 'qc_complete_and_receive':
                if order.status != 'COMPLETED':
                    alloc_code = f"{order.product.code}-{order.code}"
                    alloc_name = f"{order.product.name} [{order.code}]"
                    if order.customer_name: alloc_name += f" (ลค. {order.customer_name})"

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

                    doc_in = InventoryDoc.objects.create(doc_type='GR', reference=f"รับจาก {order.code}", description=f"รับสินค้าสำเร็จรูปจากการผลิต {order.code} (QC Pass)", created_by=request.user)
                    StockMovement.objects.create(doc=doc_in, product=allocated_product, quantity=Decimal(str(order.quantity)), movement_type='IN', created_by=request.user)

                    allocated_product.stock_qty = (allocated_product.stock_qty or Decimal('0')) + Decimal(str(order.quantity))
                    allocated_product.save()

                    order.status = 'COMPLETED'
                    order.finish_date = timezone.now().date()
                    order.is_qc_passed = True
                    messages.success(request, f"🎉 ผ่าน QC และรับ {allocated_product.name} เข้าคลังแล้ว! งานย้ายไปช่อง W4")
            else:
                messages.success(request, f"✅ อัปเดตความคืบหน้า {order.code} เรียบร้อยแล้ว!")

        is_closed = request.POST.get('is_closed')
        if is_closed == 'on':
            order.is_closed = True
            messages.success(request, f"✅ ปิดจ๊อบ {order.code} อย่างสมบูรณ์แล้ว! (ย้ายไปแท็บประวัติ)")
        elif action in ['update_progress', 'qc_complete_and_receive'] and not is_closed:
            order.is_closed = False

        order.save()

    return redirect(request.META.get('HTTP_REFERER', 'production_list'))

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

@login_required
def import_bom_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            required_columns = ['FG SKU', 'RM SKU', 'Quantity']
            if not all(col in df.columns for col in required_columns):
                messages.error(request, "❌ รูปแบบไฟล์ไม่ถูกต้อง กรุณาใช้คอลัมน์: FG SKU, RM SKU, Quantity")
                return redirect('import_bom_excel')
            with transaction.atomic():
                import_count = 0
                for _, row in df.iterrows():
                    fg_sku = str(row['FG SKU']).strip()
                    rm_sku = str(row['RM SKU']).strip()
                    try:
                        qty = Decimal(str(row['Quantity']))
                    except (ValueError, TypeError, InvalidOperation):
                        continue
                    fg_product = Product.objects.filter(code=fg_sku, product_type='FG').first()
                    if not fg_product:
                        continue
                    bom_obj, _ = BOM.objects.get_or_create(
                        product=fg_product,
                        defaults={'name': f"สูตรมาตรฐาน - {fg_product.name}"}
                     )
                    rm_product = Product.objects.filter(code=rm_sku, product_type='RM').first()
                    if rm_product:
                        BOMItem.objects.update_or_create(
                            bom=bom_obj,
                            raw_material=rm_product,
                            defaults={'quantity': qty}
                        )
                        import_count += 1
            messages.success(request, f"✅ นำเข้าข้อมูลสูตรผลิตสำเร็จทั้งหมด {import_count} รายการ")
            return redirect('import_bom_excel')
        except Exception as e:
            messages.error(request, f"❌ เกิดข้อผิดพลาด: {str(e)}")
    return render(request, 'manufacturing/import_bom.html')

@login_required
def ajax_search_raw_material(request):
    q = request.GET.get('q', '')
    products = Product.objects.filter(product_type='RM', is_active=True)
    if q: products = products.filter(Q(code__icontains=q) | Q(name__icontains=q))
    products = products.order_by('code')[:30]
    results = [{'id': p.id, 'text': f"{p.code} - {p.name}"} for p in products]
    return JsonResponse({'results': results})

# ==========================================
# 🌟 [NEW] กระดานสำหรับหัวหน้าแผนกผลิต (ช่าง) 🌟
# ==========================================
@login_required
def production_head_board(request):
    today = timezone.now().date()
    default_start = today - datetime.timedelta(days=30)
    # 🌟 [FIXED] ขยายเวลาสิ้นสุดให้ล่วงหน้าไปอีก 30 วัน เหมือนหน้า Planner 🌟
    default_end = today + datetime.timedelta(days=30)

    # 🌟 1. คำนวณวันที่ สัปดาห์ปัจจุบัน และ สัปดาห์หน้า 🌟
    current_monday = today - datetime.timedelta(days=today.weekday())
    current_sunday = current_monday + datetime.timedelta(days=6)
    next_monday = current_monday + datetime.timedelta(days=7)
    next_sunday = next_monday + datetime.timedelta(days=6)

    thai_year_curr = str(current_sunday.year + 543)[-2:]
    thai_year_next = str(next_sunday.year + 543)[-2:]

    # สร้างข้อความ เช่น "13-19/4/69"
    if current_monday.month == current_sunday.month:
        str_current_week = f"{current_monday.day}-{current_sunday.day}/{current_monday.month}/{thai_year_curr}"
    else:
        str_current_week = f"{current_monday.day}/{current_monday.month}-{current_sunday.day}/{current_sunday.month}/{thai_year_curr}"

    if next_monday.month == next_sunday.month:
        str_next_week = f"{next_monday.day}-{next_sunday.day}/{next_monday.month}/{thai_year_next}"
    else:
        str_next_week = f"{next_monday.day}/{next_monday.month}-{next_sunday.day}/{next_sunday.month}/{thai_year_next}"

    # 2. รับค่าตัวกรองจากหน้าเว็บ
    start_date = request.GET.get('start_date', default_start.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', default_end.strftime('%Y-%m-%d'))
    search_q = request.GET.get('q', '')
    search_branch = request.GET.get('branch', '')
    search_team = request.GET.get('team', '')
    search_salesperson = request.GET.get('salesperson', '')

    # 3. ดึงข้อมูลงาน (PLANNED = เตรียมเข้าใหม่, IN_PROGRESS = กำลังทำ, REWORK = ซ่อม)
    orders = ProductionOrder.objects.select_related(
        'product', 'branch', 'production_team', 'salesperson', 'salesperson__branch', 'quotation_ref'
    ).prefetch_related('completed_departments', 'qc_logs').filter(
        status__in=['PLANNED', 'IN_PROGRESS', 'REWORK'], is_closed=False
    ).order_by('start_date', '-id')

    # 🌟 4. ลอจิกจำกัดสิทธิ์การมองเห็น (Role-Based Visibility) 🌟
    emp = getattr(request.user, 'employee', None)
    is_manager = False

    if request.user.is_superuser:
        is_manager = True
    elif emp:
        rank = emp.business_rank.lower() if emp.business_rank else ""
        job_title = emp.position.title.lower() if emp.position else ""
        if rank in ['manager', 'director'] or 'manager' in job_title:
            is_manager = True

    # ถ้าไม่ใช่ผู้จัดการ และมีการระบุทีมช่าง ให้กรองเฉพาะงานของทีมตัวเอง!
    if not is_manager and emp and emp.production_team:
        orders = orders.filter(production_team=emp.production_team)

    # 5. ใส่ Filter ค้นหา
    if start_date: orders = orders.filter(start_date__gte=start_date)
    if end_date: orders = orders.filter(start_date__lte=end_date)
    if search_q:
        orders = orders.filter(Q(code__icontains=search_q) | Q(customer_name__icontains=search_q) | Q(product__name__icontains=search_q))
    if search_branch: orders = orders.filter(branch_id=search_branch)
    if search_team: orders = orders.filter(production_team_id=search_team)
    if search_salesperson: orders = orders.filter(salesperson_id=search_salesperson)

    # 🌟 6. ฟังก์ชันแปลงวันที่ ให้กลายเป็นป้ายสัปดาห์คิวงาน (บนการ์ด) 🌟
    def format_week_range(d):
        iso_y, iso_w, _ = d.isocalendar()
        monday = datetime.date.fromisocalendar(iso_y, iso_w, 1)
        sunday = monday + datetime.timedelta(days=6)
        y_str = str(sunday.year + 543)[-2:]
        if monday.month == sunday.month:
            return f"จ.{monday.day}-อา.{sunday.day}/{monday.month}/{y_str}"
        else:
            return f"จ.{monday.day}/{monday.month}-อา.{sunday.day}/{sunday.month}/{y_str}"

    # 🌟 7. แยกการ์ดออกเป็น 4 คอลัมน์ ตามเงื่อนไขเวลา 🌟
    col1_upcoming = []  # งานสัปดาห์หน้า (PLANNED)
    col2_current = []   # งานผลิตรอบปัจจุบัน (IN_PROGRESS สัปดาห์นี้)
    col3_overdue = []   # งานค้าง (IN_PROGRESS เก่ากว่าสัปดาห์นี้)
    col4_rework = []    # งานแจ้งซ่อมจาก QC (REWORK)

    for order in orders:
        order.display_cohort = format_week_range(order.start_date)
        
        if order.status == 'PLANNED':
            col1_upcoming.append(order)
        elif order.status == 'REWORK':
            col4_rework.append(order)
        elif order.status == 'IN_PROGRESS':
            # ถ้า start_date เก่ากว่าวันจันทร์ของสัปดาห์นี้ ถือว่าค้าง (Overdue)
            if order.start_date < current_monday:
                col3_overdue.append(order)
            else:
                col2_current.append(order)

    # ดึงข้อมูล Master Data สำหรับช่อง Filter
    branches = MfgBranch.objects.all().order_by('name')
    teams = ProductionTeam.objects.all().order_by('name')
    salespersons = Salesperson.objects.select_related('branch').all().order_by('name')
    prod_statuses = ProductionStatus.objects.all().order_by('sequence', 'id')

    return render(request, 'manufacturing/production_head_board.html', {
        'orders': orders, # ส่งไปให้ Modal
        'col1_upcoming': col1_upcoming,
        'col2_current': col2_current,
        'col3_overdue': col3_overdue,
        'col4_rework': col4_rework,
        'str_current_week': str_current_week,
        'str_next_week': str_next_week,
        'branches': branches,
        'teams': teams,
        'salespersons': salespersons,
        'prod_statuses': prod_statuses,
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_branch': search_branch,
        'search_team': search_team,
        'search_salesperson': search_salesperson,
    })

@login_required
def submit_to_qc(request, pk):
    # ฟังก์ชันสำหรับช่างกดส่งงานให้ QC
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status in ['IN_PROGRESS', 'REWORK']:
        order.status = 'WAITING_QC'
        order.save()
        messages.success(request, f"✅ ส่งงาน {order.code} ให้แผนก QC ตรวจสอบเรียบร้อยแล้ว!")
    return redirect('production_head_board')

# ==========================================
# 🌟 [NEW] กระดานสำหรับหัวหน้าแผนก QC (ตรวจสอบคุณภาพ) 🌟
# ==========================================
@login_required
def qc_board(request):
    today = timezone.now().date()
    default_start = today - datetime.timedelta(days=30)
    # 🌟 [FIXED] ขยายเวลาสิ้นสุดให้ล่วงหน้าไปอีก 30 วัน เหมือนหน้า Planner 🌟
    default_end = today + datetime.timedelta(days=30)

    # 🌟 1. คำนวณวันที่ สัปดาห์ปัจจุบัน 🌟
    current_monday = today - datetime.timedelta(days=today.weekday())
    current_sunday = current_monday + datetime.timedelta(days=6)
    thai_year_curr = str(current_sunday.year + 543)[-2:]

    if current_monday.month == current_sunday.month:
        str_current_week = f"{current_monday.day}-{current_sunday.day}/{current_monday.month}/{thai_year_curr}"
    else:
        str_current_week = f"{current_monday.day}/{current_monday.month}-{current_sunday.day}/{current_sunday.month}/{thai_year_curr}"

    # 2. รับค่าตัวกรองจากหน้าเว็บ
    start_date = request.GET.get('start_date', default_start.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', default_end.strftime('%Y-%m-%d'))
    search_q = request.GET.get('q', '')
    search_branch = request.GET.get('branch', '')
    search_team = request.GET.get('team', '')
    search_salesperson = request.GET.get('salesperson', '')

    # 3. ดึงข้อมูลงาน (WAITING_QC = รอตรวจ, REWORK = ตีกลับกำลังซ่อม)
    orders = ProductionOrder.objects.select_related(
        'product', 'branch', 'production_team', 'salesperson', 'salesperson__branch', 'quotation_ref'
    ).prefetch_related('qc_logs').filter(
        status__in=['WAITING_QC', 'REWORK'], is_closed=False
    ).order_by('start_date', '-id')

    # 4. ใส่ Filter ค้นหา
    if start_date: orders = orders.filter(start_date__gte=start_date)
    if end_date: orders = orders.filter(start_date__lte=end_date)
    if search_q:
        orders = orders.filter(Q(code__icontains=search_q) | Q(customer_name__icontains=search_q) | Q(product__name__icontains=search_q))
    if search_branch: orders = orders.filter(branch_id=search_branch)
    if search_team: orders = orders.filter(production_team_id=search_team)
    if search_salesperson: orders = orders.filter(salesperson_id=search_salesperson)

    # 🌟 5. ฟังก์ชันแปลงวันที่ ให้กลายเป็นป้ายสัปดาห์คิวงาน (บนการ์ด) 🌟
    def format_week_range(d):
        iso_y, iso_w, _ = d.isocalendar()
        monday = datetime.date.fromisocalendar(iso_y, iso_w, 1)
        sunday = monday + datetime.timedelta(days=6)
        y_str = str(sunday.year + 543)[-2:]
        if monday.month == sunday.month:
            return f"จ.{monday.day}-อา.{sunday.day}/{monday.month}/{y_str}"
        else:
            return f"จ.{monday.day}/{monday.month}-อา.{sunday.day}/{sunday.month}/{y_str}"

    # 🌟 6. แยกการ์ดออกเป็น 3 คอลัมน์ สำหรับกระดาน QC 🌟
    col1_current = []   # รอตรวจรอบปัจจุบัน
    col2_overdue = []   # ค้างตรวจสอบ (Overdue)
    col3_rework = []    # งานที่ถูกตีกลับ (กำลังซ่อม)

    for order in orders:
        order.display_cohort = format_week_range(order.start_date)
        
        if order.status == 'REWORK':
            col3_rework.append(order)
        elif order.status == 'WAITING_QC':
            if order.start_date < current_monday:
                col2_overdue.append(order)
            else:
                col1_current.append(order)

    # ดึงข้อมูล Master Data สำหรับช่อง Filter
    branches = MfgBranch.objects.all().order_by('name')
    teams = ProductionTeam.objects.all().order_by('name')
    salespersons = Salesperson.objects.select_related('branch').all().order_by('name')

    return render(request, 'manufacturing/qc_board.html', {
        'orders': orders,
        'col1_current': col1_current,
        'col2_overdue': col2_overdue,
        'col3_rework': col3_rework,
        'str_current_week': str_current_week,
        'branches': branches,
        'teams': teams,
        'salespersons': salespersons,
        'start_date': start_date,
        'end_date': end_date,
        'search_q': search_q,
        'search_branch': search_branch,
        'search_team': search_team,
        'search_salesperson': search_salesperson,
    })

@login_required
@transaction.atomic
def process_qc(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        # 🌟 [NEW] รับค่าจากการติ๊กกล่อง Checklist 6 ข้อ ทุกครั้งที่มีการกดปุ่มใดๆ ในฟอร์ม 🌟
        order.qc_paint = request.POST.get('qc_paint') == 'on'
        order.qc_internal = request.POST.get('qc_internal') == 'on'
        order.qc_external = request.POST.get('qc_external') == 'on'
        order.qc_electrical = request.POST.get('qc_electrical') == 'on'
        order.qc_plumbing = request.POST.get('qc_plumbing') == 'on'
        order.qc_aircon = request.POST.get('qc_aircon') == 'on'

        # 🌟 [NEW] กรณีที่ QC กดแค่ปุ่ม "บันทึกไว้ก่อน (สีเหลือง)" 🌟
        if action == 'save_progress':
            order.save()
            messages.success(request, f"💾 บันทึกความคืบหน้าการตรวจ QC สำหรับ {order.code} เรียบร้อยแล้ว! (รอตรวจต่อ)")
            return redirect('qc_board')

        # 1. 🌟 กรณีที่ QC ตรวจผ่าน 100% (รับเข้าคลัง) 🌟
        elif action == 'pass':
            alloc_code = f"{order.product.code}-{order.code}"
            alloc_name = f"{order.product.name} [{order.code}]"
            if order.customer_name: alloc_name += f" (ลค. {order.customer_name})"

            allocated_product, created = Product.objects.get_or_create(
                code=alloc_code,
                defaults={
                    'name': alloc_name[:255], 'category': order.product.category,
                    'product_type': 'FG', 'sell_price': order.product.sell_price,
                    'cost_price': order.product.cost_price, 'min_level': 0,
                    'stock_qty': 0, 'is_active': True,
                }
            )

            # บันทึกรับเข้าคลัง (Stock-In)
            doc_in = InventoryDoc.objects.create(doc_type='GR', reference=f"รับจาก {order.code}", description=f"รับสินค้าจากฝ่ายผลิต {order.code} (ผ่าน QC)", created_by=request.user)
            StockMovement.objects.create(doc=doc_in, product=allocated_product, quantity=Decimal(str(order.quantity)), movement_type='IN', created_by=request.user)

            allocated_product.stock_qty = (allocated_product.stock_qty or Decimal('0')) + Decimal(str(order.quantity))
            allocated_product.save()

            # อัปเดตสถานะงาน
            order.status = 'COMPLETED'
            order.finish_date = timezone.now().date()
            order.is_qc_passed = True
            order.save()

            messages.success(request, f"🎉 ตรวจผ่านเรียบร้อย! รับ {allocated_product.name} เข้าคลังแล้ว งานย้ายไปช่อง W4 พร้อมส่ง")

        # 2. 🌟 กรณีที่ QC ตรวจไม่ผ่าน (ตีกลับไปให้ช่างแก้) 🌟
        elif action == 'fail':
            comments = request.POST.get('comments', '')
            order.rework_count += 1
            order.status = 'REWORK' # เปลี่ยนสถานะตีกลับ

            # เก็บประวัติการตีกลับลง Log อัตโนมัติ (ไม่จำกัดจำนวนครั้ง)
            log = QCInspectionLog.objects.create(
                production_order=order,
                round_number=order.rework_count,
                inspector=getattr(request.user, 'employee', None),
                status='FAILED',
                comments=comments
            )

            if 'defect_image_1' in request.FILES:
                log.defect_image_1 = request.FILES['defect_image_1']
            if 'defect_image_2' in request.FILES:
                log.defect_image_2 = request.FILES['defect_image_2']

            log.save()
            order.save()

            messages.warning(request, f"🚨 ตีกลับงาน {order.code} ให้ช่างแก้ไขเรียบร้อยแล้ว (การตีกลับรอบที่ {order.rework_count})")

    return redirect('qc_board')