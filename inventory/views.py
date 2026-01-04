from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product

@login_required
def print_barcode(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # ถ้าสินค้าไม่มีบาร์โค้ด ให้ใช้รหัสสินค้า (Code) แทน
    barcode_val = product.barcode if product.barcode else product.code
    
    # เราจะพิมพ์ซ้ำๆ กันเต็มหน้ากระดาษ A4 (สมมติว่า 1 แผ่นมี 30 ดวง)
    # ส่ง list ตัวเลข 1-30 ไปให้ Loop ใน html
    sticker_range = range(30) 
    
    context = {
        'product': product,
        'barcode_val': barcode_val,
        'sticker_range': sticker_range
    }
    return render(request, 'inventory/barcode_print.html', context)