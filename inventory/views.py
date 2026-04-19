from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.http import JsonResponse
from django.urls import reverse
import json
from decimal import Decimal, InvalidOperation # 🌟 นำเข้า Decimal มาใช้คำนวณ

from .models import Product, StockMovement, InventoryDoc, ProductSupplier, SupplierPriceHistory
from .forms import StockInForm, StockOutForm, ProductForm, ProductSupplierFormSet
from master_data.models import CompanyInfo
from purchasing.models import PurchaseOrder, PurchaseOrderItem, OverseasPO, OverseasPOItem
from django.core.paginator import Paginator

@login_required
def inventory_dashboard(request):
    fg_qs = Product.objects.filter(is_active=True, product_type='FG')
    rm_qs = Product.objects.filter(is_active=True, product_type='RM')
    all_products = Product.objects.filter(is_active=True)
    low_stock_count = all_products.filter(stock_qty__lte=models.F('min_level')).count()

    pending_po_count = PurchaseOrder.objects.filter(status='APPROVED', receipt_status__in=['PENDING', 'PARTIAL']).count()
    pending_pq_count = OverseasPO.objects.filter(status__in=['FULLY_PAID', 'DEPOSITED']).count()

    fg_products = fg_qs.order_by('code')[:5]
    rm_products = rm_qs.order_by('code')[:5]
    recent_docs = InventoryDoc.objects.all().order_by('-doc_no')[:10]

    return render(request, 'inventory/dashboard.html', {
        'fg_products': fg_products, 'rm_products': rm_products,
        'fg_count': fg_qs.count(), 'rm_count': rm_qs.count(),       
        'low_stock_count': low_stock_count, 'recent_docs': recent_docs,
        'pending_po_count': pending_po_count,
        'pending_pq_count': pending_pq_count 
    })

@login_required
def product_list(request):
    p_type = request.GET.get('type', 'FG')
    search_query = request.GET.get('q', '')
    products = Product.objects.filter(is_active=True, product_type=p_type).order_by('code')

    if search_query:
        products = products.filter(Q(code__icontains=search_query) | Q(name__icontains=search_query) | Q(category__name__icontains=search_query))
    
    paginator = Paginator(products, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    title = '📦 คลังสินค้าสำเร็จรูป (FG)' if p_type == 'FG' else '🧱 คลังวัตถุดิบ (RM)'
    
    return render(request, 'inventory/product_list.html', {'page_obj': page_obj, 'p_type': p_type, 'title': title, 'search_query': search_query})

@login_required
def document_list_in(request): return document_list_base(request, doc_type='GR', title='ประวัติใบรับสินค้า/วัตถุดิบ (Stock In)')

@login_required
def document_list_out(request): return document_list_base(request, doc_type='GI', title='ประวัติใบเบิกสินค้า/วัตถุดิบ (Stock Out)')

def document_list_base(request, doc_type, title):
    search_query = request.GET.get('q', '')
    product_type = request.GET.get('product_type', '')
    date_start = request.GET.get('start', '')
    date_end = request.GET.get('end', '')

    docs = InventoryDoc.objects.filter(doc_type=doc_type).order_by('-doc_no')
    if product_type: docs = docs.filter(movements__product__product_type=product_type).distinct()
    if date_start: docs = docs.filter(created_at__date__gte=parse_date(date_start))
    if date_end: docs = docs.filter(created_at__date__lte=parse_date(date_end))
    if search_query: docs = docs.filter(Q(doc_no__icontains=search_query) | Q(reference__icontains=search_query) | Q(created_by__first_name__icontains=search_query))

    return render(request, 'inventory/document_list.html', {
        'docs': docs, 'title': title, 'doc_type': doc_type, 'search_query': search_query,
        'product_type': product_type, 'date_start': date_start, 'date_end': date_end,
    })

@login_required
def stock_in(request):
    if request.method == 'POST':
        form = StockInForm(request.POST)
        if form.is_valid():
            doc = InventoryDoc.objects.create(doc_type='GR', reference=form.cleaned_data['doc_reference'], description=form.cleaned_data['doc_note'], created_by=request.user)
            move = form.save(commit=False)
            move.doc = doc
            move.movement_type = 'IN'
            move.created_by = request.user
            move.save()
            messages.success(request, f"✅ เปิดใบรับของ {doc.doc_no} สำเร็จ!")
            return redirect('inventory_dashboard')
    else: form = StockInForm()
    return render(request, 'inventory/stock_form.html', {'form': form, 'title': '📥 รับสินค้าเข้า (เปิดใบรับ GR)', 'btn_color': 'success', 'btn_icon': 'fa-download'})

@login_required
def stock_out(request):
    if request.method == 'POST':
        form = StockOutForm(request.POST)
        if form.is_valid():
            move = form.save(commit=False)
            if move.product.stock_qty >= move.quantity:
                doc = InventoryDoc.objects.create(doc_type='GI', reference=form.cleaned_data['doc_reference'], description=form.cleaned_data['doc_note'], created_by=request.user)
                move.doc = doc
                move.movement_type = 'OUT'
                move.created_by = request.user
                move.save()
                messages.warning(request, f"📤 เปิดใบเบิก {doc.doc_no} สำเร็จ!")
                return redirect('inventory_dashboard')
            else:
                messages.error(request, f"❌ สต็อกไม่พอ! มีแค่ {move.product.stock_qty} ชิ้น")
    else: form = StockOutForm()
    return render(request, 'inventory/stock_form.html', {'form': form, 'title': '📦 เบิกสินค้าออก (เปิดใบเบิก GI)', 'btn_color': 'warning', 'btn_icon': 'fa-upload'})

@login_required
@transaction.atomic
def product_create(request):
    p_type = request.GET.get('type')
    
    from_pq = request.GET.get('from_pq')
    pq_item_id = request.GET.get('pq_item')
    auto_name = ""
    auto_price = 0
    if from_pq and pq_item_id:
        pq_item = OverseasPOItem.objects.filter(id=pq_item_id).first()
        if pq_item:
            auto_name = pq_item.description
            auto_price = pq_item.unit_price

    if not p_type: return render(request, 'inventory/product_type_select.html')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        formset = ProductSupplierFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            product = form.save(commit=False)
            product.product_type = p_type
            product.save()
            formset.instance = product
            formset.save()
            
            for sup in product.multi_suppliers.all():
                SupplierPriceHistory.objects.create(
                    product=product, supplier=sup.supplier,
                    old_price=0, new_price=sup.cost_price, updated_by=request.user
                )
            messages.success(request, f"✅ สร้าง '{product.name}' เรียบร้อย")
            
            if from_pq and pq_item_id:
                pq_item = OverseasPOItem.objects.filter(id=pq_item_id).first()
                if pq_item:
                    pq_item.product = product
                    pq_item.save()
                    messages.success(request, f"🔗 ผูกรหัสสินค้ากับใบสั่งซื้อ PQ สำเร็จแล้ว!")
                    return redirect('pq_receive_process', pq_id=from_pq)

            return redirect(f"{reverse('product_list')}?type={p_type}")
    else:
        form = ProductForm(initial={'product_type': p_type, 'name': auto_name, 'cost_price': auto_price})
        form.fields['product_type'].widget = forms.HiddenInput()
        formset = ProductSupplierFormSet()

    title = '✨ เพิ่มสินค้าสำเร็จรูป (FG)' if p_type == 'FG' else '✨ เพิ่มวัตถุดิบ (RM)'
    if from_pq: title = '🚨 บังคับสร้างรหัสสินค้าใหม่ (จากใบสั่งซื้อต่างประเทศ)'
    
    return render(request, 'inventory/product_form.html', {'form': form, 'formset': formset, 'title': title, 'p_type': p_type})

@login_required
@transaction.atomic
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    p_type = product.product_type
    old_prices = {sup.id: sup.cost_price for sup in product.multi_suppliers.all()}

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = ProductSupplierFormSet(request.POST, instance=product)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            for sup in product.multi_suppliers.all():
                old_p = old_prices.get(sup.id, 0)
                if old_p != sup.cost_price:
                    SupplierPriceHistory.objects.create(
                        product=product, supplier=sup.supplier,
                        old_price=old_p, new_price=sup.cost_price, updated_by=request.user
                    )
            messages.success(request, f"💾 บันทึกแก้ไข '{product.name}' เรียบร้อย")
            return redirect(f"{reverse('product_list')}?type={p_type}")
    else:
        form = ProductForm(instance=product)
        formset = ProductSupplierFormSet(instance=product)
        
    return render(request, 'inventory/product_form.html', {'form': form, 'formset': formset, 'title': f'✏️ แก้ไข: {product.name}', 'p_type': p_type})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    p_type = product.product_type
    if product.stockmovement_set.exists(): 
        messages.error(request, f"❌ ลบไม่ได้! มีประวัติการเคลื่อนไหวแล้ว")
    else:
        product.delete()
        messages.success(request, f"🗑️ ลบเรียบร้อย")
    return redirect(f"{reverse('product_list')}?type={p_type}")

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
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def ajax_add_rm_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            if name:
                RMCatModel = Product._meta.get_field('rm_category').related_model
                obj, created = RMCatModel.objects.get_or_create(name=name)
                return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def ajax_add_supplier(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            if name:
                SupplierModel = Product._meta.get_field('supplier').related_model
                obj, created = SupplierModel.objects.get_or_create(
                    name=name,
                    defaults={
                        'tax_id': data.get('tax_id', ''),
                        'contact_name': data.get('contact_name', ''),
                        'phone': data.get('phone', ''),
                        'email': data.get('email', ''),
                        'address': data.get('address', ''),
                        'credit_term': data.get('credit_term') or 0
                    }
                )
                return JsonResponse({'success': True, 'id': obj.id, 'name': obj.name})
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# ==========================================
# 🌟 ระบบรับสินค้าจาก PO ภายในประเทศ (GR) 🌟
# ==========================================
@login_required
def po_receive_list(request):
    pending_pos = PurchaseOrder.objects.filter(status='APPROVED', receipt_status__in=['PENDING', 'PARTIAL']).order_by('expected_date', '-id')
    return render(request, 'inventory/po_receive_list.html', {'pos': pending_pos})

@login_required
@transaction.atomic 
def po_receive_process(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id, status='APPROVED')
    if request.method == 'POST':
        reference_doc = request.POST.get('reference_doc', '')
        note = request.POST.get('note', '')
        items_to_receive = []
        has_error = False
        for item in po.items.all():
            input_name = f"qty_{item.id}"
            receive_val = request.POST.get(input_name, '0')
            try: 
                receive_qty = Decimal(receive_val.replace(',', ''))
            except (ValueError, InvalidOperation): 
                receive_qty = Decimal('0')
                
            if receive_qty > 0:
                remaining = Decimal(str(item.quantity)) - Decimal(str(item.received_qty))
                if receive_qty > remaining:
                    messages.error(request, f"❌ รับของเกิน! {item.product.name} สั่ง {item.quantity} (รับได้อีกไม่เกิน {remaining})")
                    has_error = True
                    break
                items_to_receive.append({'item_obj': item, 'receive_qty': receive_qty})
                
        if not has_error and items_to_receive:
            doc = InventoryDoc.objects.create(doc_type='GR', po_reference=po, reference=reference_doc, description=note, created_by=request.user)
            for data in items_to_receive:
                item = data['item_obj']
                qty = data['receive_qty']
                StockMovement.objects.create(doc=doc, product=item.product, quantity=qty, movement_type='IN', created_by=request.user)
                
                # 🌟 [FIX] บวกยอดสต็อกเข้าชั้นวางจริงๆ 🌟
                item.product.stock_qty = (item.product.stock_qty or Decimal('0')) + qty
                item.product.save()
                
                # อัปเดตยอดรับแล้วในบิล PO
                item.received_qty = Decimal(str(item.received_qty)) + qty
                item.save()
                
            po.refresh_from_db()
            all_completed = True
            any_received = False
            for item in po.items.all():
                if Decimal(str(item.received_qty)) > 0: any_received = True
                if Decimal(str(item.received_qty)) < Decimal(str(item.quantity)): all_completed = False
                
            if all_completed: po.receipt_status = 'COMPLETED'
            elif any_received: po.receipt_status = 'PARTIAL'
            po.save()
            messages.success(request, f"✅ รับสินค้าจาก PO: {po.code} สำเร็จ! (เลขที่ใบรับ: {doc.doc_no})")
            return redirect('print_document', doc_no=doc.doc_no)
        elif not items_to_receive and not has_error:
            messages.warning(request, "⚠️ กรุณาระบุจำนวนสินค้าที่ต้องการรับอย่างน้อย 1 รายการ")
    return render(request, 'inventory/po_receive_form.html', {'po': po})


# ==========================================
# 🌟 ระบบรับสินค้าจาก PQ ต่างประเทศ (GR) 🌟
# ==========================================
@login_required
def pq_receive_list(request):
    pending_pqs = OverseasPO.objects.filter(status__in=['FULLY_PAID', 'DEPOSITED']).order_by('eta_date', '-id')
    return render(request, 'inventory/pq_receive_list.html', {'pos': pending_pqs})

@login_required
@transaction.atomic 
def pq_receive_process(request, pq_id):
    pq = get_object_or_404(OverseasPO, id=pq_id, status__in=['FULLY_PAID', 'DEPOSITED'])
    
    unlinked_items = []
    for item in pq.overseas_items.all():
        if not item.product: 
            unlinked_items.append(item)
            
    if unlinked_items:
        messages.warning(request, f"🚨 บิล PQ นี้มีรายการ 'พิมพ์เพิ่มเอง' ที่ยังไม่ได้สร้างรหัสในระบบคลัง! กรุณาสร้างรหัสก่อนรับสินค้าเข้าคลังค่ะ")
        return render(request, 'inventory/pq_force_create_product.html', {'pq': pq, 'unlinked_items': unlinked_items})

    if request.method == 'POST':
        reference_doc = request.POST.get('reference_doc', pq.pi_number) 
        note = request.POST.get('note', f'รับสินค้าจากใบสั่งซื้อต่างประเทศ {pq.po_number}')
        
        doc = InventoryDoc.objects.create(doc_type='GR', reference=reference_doc, description=note, created_by=request.user)
        for item in pq.overseas_items.all():
            if item.product and item.quantity > 0:
                qty_decimal = Decimal(str(item.quantity))
                StockMovement.objects.create(doc=doc, product=item.product, quantity=qty_decimal, movement_type='IN', created_by=request.user)
                
                # 🌟 [FIX] บวกยอดสต็อกเข้าชั้นวางจริงๆ 🌟
                item.product.stock_qty = (item.product.stock_qty or Decimal('0')) + qty_decimal
                item.product.save()
                 
        pq.status = 'COMPLETED'
        pq.save()
        messages.success(request, f"✅ รับสินค้าจาก PQ: {pq.po_number} เข้าคลังสำเร็จ! (เลขที่ใบรับ: {doc.doc_no})")
        return redirect('print_document', doc_no=doc.doc_no)
        
    return render(request, 'inventory/pq_receive_form.html', {'po': pq})