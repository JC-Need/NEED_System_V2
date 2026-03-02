from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.http import JsonResponse
import json

from .models import Product, StockMovement, InventoryDoc
from .forms import StockInForm, StockOutForm, ProductForm
from master_data.models import CompanyInfo
# 🌟 ดึงข้อมูล PO จากฝั่งจัดซื้อมาใช้ 🌟
from purchasing.models import PurchaseOrder, PurchaseOrderItem

@login_required
def inventory_dashboard(request):
    fg_products = Product.objects.filter(is_active=True, product_type='FG').order_by('code')
    rm_products = Product.objects.filter(is_active=True, product_type='RM').order_by('code')
    all_products = Product.objects.filter(is_active=True)
    low_stock_count = all_products.filter(stock_qty__lte=models.F('min_level')).count()

    recent_docs = InventoryDoc.objects.all().order_by('-doc_no')[:10]

    return render(request, 'inventory/dashboard.html', {
        'fg_products': fg_products,
        'rm_products': rm_products,
        'low_stock_count': low_stock_count,
        'recent_docs': recent_docs
    })

@login_required
def document_list_in(request):
    return document_list_base(request, doc_type='GR', title='ประวัติใบรับสินค้า/วัตถุดิบ (Stock In)')

@login_required
def document_list_out(request):
    return document_list_base(request, doc_type='GI', title='ประวัติใบเบิกสินค้า/วัตถุดิบ (Stock Out)')

def document_list_base(request, doc_type, title):
    search_query = request.GET.get('q', '')
    product_type = request.GET.get('product_type', '') 
    date_start = request.GET.get('start', '')
    date_end = request.GET.get('end', '')

    docs = InventoryDoc.objects.filter(doc_type=doc_type).order_by('-doc_no')

    if product_type:
        docs = docs.filter(movements__product__product_type=product_type).distinct()

    if date_start:
        docs = docs.filter(created_at__date__gte=parse_date(date_start))
    if date_end:
        docs = docs.filter(created_at__date__lte=parse_date(date_end))

    if search_query:
        docs = docs.filter(
            Q(doc_no__icontains=search_query) |
            Q(reference__icontains=search_query) |
            Q(created_by__first_name__icontains=search_query)
        )

    return render(request, 'inventory/document_list.html', {
        'docs': docs,
        'title': title,
        'doc_type': doc_type,
        'search_query': search_query,
        'product_type': product_type,
        'date_start': date_start,
        'date_end': date_end,
    })

@login_required
def stock_in(request):
    if request.method == 'POST':
        form = StockInForm(request.POST)
        if form.is_valid():
            doc = InventoryDoc.objects.create(
                doc_type='GR',
                reference=form.cleaned_data['doc_reference'],
                description=form.cleaned_data['doc_note'],
                created_by=request.user
            )
            move = form.save(commit=False)
            move.doc = doc
            move.movement_type = 'IN'
            move.created_by = request.user
            move.save()
            messages.success(request, f"✅ เปิดใบรับของ {doc.doc_no} สำเร็จ!")
            return redirect('inventory_dashboard') 
    else:
        form = StockInForm()
    return render(request, 'inventory/stock_form.html', {'form': form, 'title': '📥 รับสินค้าเข้า (เปิดใบรับ GR)', 'btn_color': 'success', 'btn_icon': 'fa-download'})

@login_required
def stock_out(request):
    if request.method == 'POST':
        form = StockOutForm(request.POST)
        if form.is_valid():
            move = form.save(commit=False)
            if move.product.stock_qty >= move.quantity:
                doc = InventoryDoc.objects.create(
                    doc_type='GI',
                    reference=form.cleaned_data['doc_reference'],
                    description=form.cleaned_data['doc_note'],
                    created_by=request.user
                )
                move.doc = doc
                move.movement_type = 'OUT'
                move.created_by = request.user
                move.save()
                messages.warning(request, f"📤 เปิดใบเบิก {doc.doc_no} สำเร็จ!")
                return redirect('inventory_dashboard')
            else:
                messages.error(request, f"❌ สต็อกไม่พอ! มีแค่ {move.product.stock_qty} ชิ้น")
    else:
        form = StockOutForm()
    return render(request, 'inventory/stock_form.html', {'form': form, 'title': '📦 เบิกสินค้าออก (เปิดใบเบิก GI)', 'btn_color': 'warning', 'btn_icon': 'fa-upload'})

@login_required
def product_create(request):
    p_type = request.GET.get('type')

    if not p_type:
        return render(request, 'inventory/product_type_select.html')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.product_type = p_type 
            product.save()
            messages.success(request, f"✅ สร้าง '{product.name}' เรียบร้อย")
            return redirect('inventory_dashboard')
    else:
        form = ProductForm(initial={'product_type': p_type})
        form.fields['product_type'].widget = forms.HiddenInput()

    title = '✨ เพิ่มสินค้าสำเร็จรูป (FG)' if p_type == 'FG' else '✨ เพิ่มวัตถุดิบ (RM)'
    return render(request, 'inventory/product_form.html', {'form': form, 'title': title})

@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"💾 บันทึกแก้ไข '{product.name}' เรียบร้อย")
            return redirect('inventory_dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'title': f'✏️ แก้ไข: {product.name}'})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.stockmovement_set.exists():
        messages.error(request, f"❌ ลบไม่ได้! มีประวัติการเคลื่อนไหวแล้ว")
    else:
        product.delete()
        messages.success(request, f"🗑️ ลบเรียบร้อย")
    return redirect('inventory_dashboard')

@login_required
def print_barcode(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    barcode_val = product.barcode if product.barcode else product.code
    return render(request, 'inventory/barcode_print.html', {'product': product, 'barcode_val': barcode_val, 'sticker_range': range(30)})

@login_required
def print_document(request, doc_no):
    doc = get_object_or_404(InventoryDoc, doc_no=doc_no)
    company = CompanyInfo.objects.first()
    return render(request, 'inventory/doc_print.html', {'doc': doc, 'company': company})

@login_required
def ajax_add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            if name:
                CategoryModel = Product._meta.get_field('category').related_model
                obj, created = CategoryModel.objects.get_or_create(name=name)
                return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def ajax_add_supplier(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            if name:
                SupplierModel = Product._meta.get_field('supplier').related_model
                obj, created = SupplierModel.objects.get_or_create(name=name)
                return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# ==========================================
# 🌟 ระบบรับสินค้าจากใบสั่งซื้อ (Receive from PO) 🌟
# ==========================================
@login_required
def po_receive_list(request):
    """ แสดงรายการใบสั่งซื้อที่รอการรับสินค้า (เฉพาะที่อนุมัติแล้ว และยังรับของไม่ครบ) """
    pending_pos = PurchaseOrder.objects.filter(
        status='APPROVED',
        receipt_status__in=['PENDING', 'PARTIAL']
    ).order_by('expected_date', '-id')
    return render(request, 'inventory/po_receive_list.html', {'pos': pending_pos})

@login_required
@transaction.atomic # ป้องกันข้อมูลพังถ้าระบบขัดข้องระหว่างบันทึก
def po_receive_process(request, po_id):
    """ หน้าฟอร์มให้พนักงานคลังสินค้ากรอกยอดรับจริง """
    po = get_object_or_404(PurchaseOrder, id=po_id, status='APPROVED')

    if request.method == 'POST':
        reference_doc = request.POST.get('reference_doc', '')
        note = request.POST.get('note', '')
        
        items_to_receive = []
        has_error = False

        # ตรวจสอบตัวเลขที่รับเข้าว่าไม่เกินยอดที่สั่ง
        for item in po.items.all():
            input_name = f"qty_{item.id}"
            receive_val = request.POST.get(input_name, '0')
            try:
                receive_qty = float(receive_val.replace(',', ''))
            except ValueError:
                receive_qty = 0

            if receive_qty > 0:
                remaining = float(item.quantity) - float(item.received_qty)
                if receive_qty > remaining:
                    messages.error(request, f"❌ รับของเกิน! {item.product.name} สั่ง {item.quantity} (รับได้อีกไม่เกิน {remaining})")
                    has_error = True
                    break
                items_to_receive.append({'item_obj': item, 'receive_qty': receive_qty})

        if not has_error and items_to_receive:
            # 1. สร้างหัวเอกสารรับเข้า (GR)
            doc = InventoryDoc.objects.create(
                doc_type='GR',
                po_reference=po,
                reference=reference_doc,
                description=note,
                created_by=request.user
            )

            # 2. บันทึกประวัติเคลื่อนไหว (พร้อมบวกสต็อกอัตโนมัติ) และอัปเดตยอดรับในรายการ PO
            for data in items_to_receive:
                item = data['item_obj']
                qty = data['receive_qty']

                StockMovement.objects.create(
                    doc=doc,
                    product=item.product,
                    quantity=qty,
                    movement_type='IN',
                    created_by=request.user
                )

                item.received_qty = float(item.received_qty) + float(qty)
                item.save()

            # 3. อัปเดตสถานะรับของ (Receipt Status) ของใบ PO หลัก
            po.refresh_from_db()
            all_completed = True
            any_received = False
            
            for item in po.items.all():
                if float(item.received_qty) > 0:
                    any_received = True
                if float(item.received_qty) < float(item.quantity):
                    all_completed = False

            if all_completed:
                po.receipt_status = 'COMPLETED'
            elif any_received:
                po.receipt_status = 'PARTIAL'
            po.save()

            messages.success(request, f"✅ รับสินค้าจาก PO: {po.code} สำเร็จ! (เลขที่ใบรับ: {doc.doc_no})")
            return redirect('po_receive_list')
            
        elif not items_to_receive and not has_error:
            messages.warning(request, "⚠️ กรุณาระบุจำนวนสินค้าที่ต้องการรับอย่างน้อย 1 รายการ")

    return render(request, 'inventory/po_receive_form.html', {'po': po})