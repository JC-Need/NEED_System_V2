from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from .models import Product, StockMovement, InventoryDoc
from .forms import StockInForm, StockOutForm, ProductForm
from master_data.models import CompanyInfo  # ✅ 1. เพิ่มบรรทัดนี้เพื่อเรียกใช้ข้อมูลบริษัท

@login_required
def inventory_dashboard(request):
    fg_products = Product.objects.filter(is_active=True, product_type='FG').order_by('code')
    rm_products = Product.objects.filter(is_active=True, product_type='RM').order_by('code')

    all_products = Product.objects.filter(is_active=True)
    low_stock_count = all_products.filter(stock_qty__lte=models.F('min_level')).count()

    # ดึงข้อมูล "เอกสาร" ล่าสุดมาโชว์ (GR/GI)
    recent_docs = InventoryDoc.objects.all().order_by('-created_at')[:10]

    return render(request, 'inventory/dashboard.html', {
        'fg_products': fg_products,
        'rm_products': rm_products,
        'low_stock_count': low_stock_count,
        'recent_docs': recent_docs
    })

@login_required
def stock_in(request):
    if request.method == 'POST':
        form = StockInForm(request.POST)
        if form.is_valid():
            # 1. สร้างหัวเอกสาร (Goods Receipt - GR)
            doc = InventoryDoc.objects.create(
                doc_type='GR',
                reference=form.cleaned_data['doc_reference'],
                description=form.cleaned_data['doc_note'],
                created_by=request.user
            )

            # 2. สร้างรายการสินค้า ผูกกับเอกสารนี้
            move = form.save(commit=False)
            move.doc = doc
            move.movement_type = 'IN'
            move.created_by = request.user
            move.save() # (Stock จะถูกบวกเองใน models.py)

            messages.success(request, f"✅ เปิดใบรับของ {doc.doc_no} สำเร็จ!")
            return redirect('inventory_dashboard')
    else:
        form = StockInForm()

    return render(request, 'inventory/stock_form.html', {
        'form': form,
        'title': '📥 รับสินค้าเข้า (เปิดใบรับ GR)',
        'btn_color': 'success',
        'btn_icon': 'fa-download'
    })

@login_required
def stock_out(request):
    if request.method == 'POST':
        form = StockOutForm(request.POST)
        if form.is_valid():
            move = form.save(commit=False)

            # เช็คสต็อกก่อนว่าพอไหม
            if move.product.stock_qty >= move.quantity:
                # 1. สร้างหัวเอกสาร (Goods Issue - GI)
                doc = InventoryDoc.objects.create(
                    doc_type='GI',
                    reference=form.cleaned_data['doc_reference'],
                    description=form.cleaned_data['doc_note'],
                    created_by=request.user
                )

                # 2. สร้างรายการสินค้า ผูกกับเอกสาร
                move.doc = doc
                move.movement_type = 'OUT'
                move.created_by = request.user
                move.save() # (Stock จะถูกตัดเองใน models.py)

                messages.warning(request, f"📤 เปิดใบเบิก {doc.doc_no} สำเร็จ!")
                return redirect('inventory_dashboard')
            else:
                messages.error(request, f"❌ สต็อกไม่พอ! มีแค่ {move.product.stock_qty} ชิ้น")
    else:
        form = StockOutForm()

    return render(request, 'inventory/stock_form.html', {
        'form': form,
        'title': '📦 เบิกสินค้าออก (เปิดใบเบิก GI)',
        'btn_color': 'warning',
        'btn_icon': 'fa-upload'
    })

@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"✅ สร้าง '{product.name}' เรียบร้อย (รหัส: {product.code})")
            return redirect('inventory_dashboard')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': '✨ ลงทะเบียนสินค้า/วัตถุดิบใหม่'})

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
    # ดึงข้อมูลเอกสารตามเลขที่ (doc_no)
    doc = get_object_or_404(InventoryDoc, doc_no=doc_no)
    
    # ✅ 2. ดึงข้อมูลบริษัท (เอาอันแรกที่เจอ)
    company = CompanyInfo.objects.first()

    return render(request, 'inventory/doc_print.html', {
        'doc': doc,
        'company': company, # ✅ 3. ส่งข้อมูลบริษัทไปที่หน้าจอ
    })