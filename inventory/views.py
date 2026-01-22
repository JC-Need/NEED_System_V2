from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.utils.dateparse import parse_date
from .models import Product, StockMovement, InventoryDoc
from .forms import StockInForm, StockOutForm, ProductForm
from master_data.models import CompanyInfo

@login_required
def inventory_dashboard(request):
    fg_products = Product.objects.filter(is_active=True, product_type='FG').order_by('code')
    rm_products = Product.objects.filter(is_active=True, product_type='RM').order_by('code')
    all_products = Product.objects.filter(is_active=True)
    low_stock_count = all_products.filter(stock_qty__lte=models.F('min_level')).count()

    # ดึงแค่ 10 รายการล่าสุด (รวมทุกประเภท)
    recent_docs = InventoryDoc.objects.all().order_by('-doc_no')[:10]

    return render(request, 'inventory/dashboard.html', {
        'fg_products': fg_products,
        'rm_products': rm_products,
        'low_stock_count': low_stock_count,
        'recent_docs': recent_docs
    })

# ✅ ฟังก์ชันใหม่: รายการใบรับสินค้า (Goods Receipt List)
@login_required
def document_list_in(request):
    return document_list_base(request, doc_type='GR', title='ประวัติใบรับสินค้า/วัตถุดิบ (Stock In)')

# ✅ ฟังก์ชันใหม่: รายการใบเบิกสินค้า (Goods Issue List)
@login_required
def document_list_out(request):
    return document_list_base(request, doc_type='GI', title='ประวัติใบเบิกสินค้า/วัตถุดิบ (Stock Out)')

# ⚙️ ฟังก์ชันกลางสำหรับกรองและค้นหา (Core Logic)
def document_list_base(request, doc_type, title):
    # รับค่าจาก Filter
    search_query = request.GET.get('q', '')
    product_type = request.GET.get('product_type', '') # FG หรือ RM
    date_start = request.GET.get('start', '')
    date_end = request.GET.get('end', '')

    # 1. กรองประเภทเอกสารก่อน (GR หรือ GI)
    docs = InventoryDoc.objects.filter(doc_type=doc_type).order_by('-doc_no')

    # 2. กรองตามประเภทสินค้า (FG/RM)
    # (เช็คว่าในเอกสารใบนั้น มีสินค้าประเภทที่เลือกอยู่หรือไม่)
    if product_type:
        docs = docs.filter(movements__product__product_type=product_type).distinct()

    # 3. กรองตามช่วงเวลา
    if date_start:
        docs = docs.filter(created_at__date__gte=parse_date(date_start))
    if date_end:
        docs = docs.filter(created_at__date__lte=parse_date(date_end))

    # 4. ค้นหาทั่วไป
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
        # ส่งค่ากลับไปแปะในฟอร์ม search
        'search_query': search_query,
        'product_type': product_type,
        'date_start': date_start,
        'date_end': date_end,
    })

# ... (ส่วน Stock In/Out, Product, Print Barcode, Print Doc คงไว้เหมือนเดิม) ...
@login_required
def stock_in(request):
    # (โค้ดเดิม...)
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
            return redirect('inventory_dashboard') # กลับไป Dashboard หรือหน้า List ก็ได้
    else:
        form = StockInForm()
    return render(request, 'inventory/stock_form.html', {'form': form, 'title': '📥 รับสินค้าเข้า (เปิดใบรับ GR)', 'btn_color': 'success', 'btn_icon': 'fa-download'})

@login_required
def stock_out(request):
    # (โค้ดเดิม...)
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
    # รับค่า type จาก URL
    p_type = request.GET.get('type')

    # 1. ถ้ายังไม่ได้เลือก Type -> ไปหน้าเลือกก่อน
    if not p_type:
        return render(request, 'inventory/product_type_select.html')

    # 2. ถ้าเลือกแล้ว -> สร้างฟอร์ม
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.product_type = p_type # บังคับค่าตามที่เลือก
            product.save()
            messages.success(request, f"✅ สร้าง '{product.name}' เรียบร้อย")
            return redirect('inventory_dashboard')
    else:
        # กำหนดค่าเริ่มต้น และซ่อนช่องเลือกประเภท
        form = ProductForm(initial={'product_type': p_type})
        form.fields['product_type'].widget = forms.HiddenInput()

    title = '✨ เพิ่มสินค้าสำเร็จรูป (FG)' if p_type == 'FG' else '✨ เพิ่มวัตถุดิบ (RM)'
    return render(request, 'inventory/product_form.html', {'form': form, 'title': title})

@login_required
def product_update(request, pk):
    # (โค้ดเดิม...)
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
    # (โค้ดเดิม...)
    product = get_object_or_404(Product, pk=pk)
    if product.stockmovement_set.exists():
        messages.error(request, f"❌ ลบไม่ได้! มีประวัติการเคลื่อนไหวแล้ว")
    else:
        product.delete()
        messages.success(request, f"🗑️ ลบเรียบร้อย")
    return redirect('inventory_dashboard')

@login_required
def print_barcode(request, product_id):
    # (โค้ดเดิม...)
    product = get_object_or_404(Product, id=product_id)
    barcode_val = product.barcode if product.barcode else product.code
    return render(request, 'inventory/barcode_print.html', {'product': product, 'barcode_val': barcode_val, 'sticker_range': range(30)})

@login_required
def print_document(request, doc_no):
    # (โค้ดเดิม...)
    doc = get_object_or_404(InventoryDoc, doc_no=doc_no)
    company = CompanyInfo.objects.first()
    return render(request, 'inventory/doc_print.html', {'doc': doc, 'company': company})