from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models  # ✅ เพิ่มบรรทัดนี้ครับ (ตัวแก้ Error)
from .models import Product, StockMovement
from .forms import StockInForm, StockOutForm, ProductForm

# ==========================================
# 1. หน้า Dashboard รวมสต็อก
# ==========================================
@login_required
def inventory_dashboard(request):
    # ดึงสินค้าทั้งหมด เรียงตามหมวดหมู่
    products = Product.objects.filter(is_active=True).order_by('category', 'name')
    
    # นับสินค้าที่ใกล้หมด (Low Stock) โดยใช้ models.F
    low_stock_count = products.filter(stock_qty__lte=models.F('min_level')).count()

    # ดึงประวัติการเคลื่อนไหวล่าสุด 10 รายการ
    recent_movements = StockMovement.objects.all().order_by('-created_at')[:10]

    return render(request, 'inventory/dashboard.html', {
        'products': products,
        'low_stock_count': low_stock_count,
        'recent_movements': recent_movements
    })

# ==========================================
# 2. ฟังก์ชันรับเข้า (Stock In)
# ==========================================
@login_required
def stock_in(request):
    if request.method == 'POST':
        form = StockInForm(request.POST)
        if form.is_valid():
            move = form.save(commit=False)
            move.movement_type = 'IN'      # กำหนดขาเข้า
            move.created_by = request.user 
            move.save()                    # models.py จะไปบวกยอด stock_qty ให้เอง
            
            messages.success(request, f"✅ รับเข้า '{move.product.name}' จำนวน {move.quantity} สำเร็จ")
            return redirect('inventory_dashboard')
    else:
        form = StockInForm()
    
    return render(request, 'inventory/stock_form.html', {
        'form': form, 
        'title': '📦 รับสินค้าเข้าคลัง (Stock In)',
        'btn_color': 'success',
        'btn_icon': 'fa-download'
    })

# ==========================================
# 3. ฟังก์ชันเบิกออก (Stock Out)
# ==========================================
@login_required
def stock_out(request):
    if request.method == 'POST':
        form = StockOutForm(request.POST)
        if form.is_valid():
            move = form.save(commit=False)
            
            # เช็คก่อนว่ามีของพอให้เบิกไหม?
            if move.product.stock_qty >= move.quantity:
                move.movement_type = 'OUT' # กำหนดขาออก
                move.created_by = request.user
                move.save() # models.py จะไปลบยอด stock_qty ให้เอง
                
                messages.warning(request, f"📤 เบิกจ่าย '{move.product.name}' จำนวน {move.quantity} สำเร็จ")
                return redirect('inventory_dashboard')
            else:
                messages.error(request, f"❌ ทำรายการไม่สำเร็จ! สินค้ามีแค่ {move.product.stock_qty} ชิ้น")
    else:
        form = StockOutForm()

    return render(request, 'inventory/stock_form.html', {
        'form': form, 
        'title': '🚚 เบิกจ่ายสินค้า (Stock Out)',
        'btn_color': 'warning',
        'btn_icon': 'fa-upload'
    })

# ==========================================
# 4. พิมพ์บาร์โค้ด
# ==========================================
@login_required
def print_barcode(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    barcode_val = product.barcode if product.barcode else product.code
    sticker_range = range(30) 
    context = {
        'product': product,
        'barcode_val': barcode_val,
        'sticker_range': sticker_range
    }
    return render(request, 'inventory/barcode_print.html', context)

# ==========================================
# 5. จัดการสินค้า (Product Management)
# ==========================================
@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"✅ สร้างสินค้า '{product.name}' เรียบร้อยแล้ว")
            return redirect('inventory_dashboard')
    else:
        form = ProductForm()
    
    return render(request, 'inventory/product_form.html', {
        'form': form, 'title': '✨ ลงทะเบียนสินค้าใหม่'
    })

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
        
    return render(request, 'inventory/product_form.html', {
        'form': form, 'title': f'✏️ แก้ไขสินค้า: {product.name}'
    })

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.stockmovement_set.exists():
        messages.error(request, f"❌ ลบไม่ได้! สินค้านี้มีประวัติการเคลื่อนไหวแล้ว (ให้ปิดการใช้งานแทน)")
    else:
        product.delete()
        messages.success(request, f"🗑️ ลบสินค้าเรียบร้อย")
    return redirect('inventory_dashboard')