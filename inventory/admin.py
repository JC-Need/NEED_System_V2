from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # ✅ เพิ่ม 'show_image' เข้าไปใน list_display (ตรงตำแหน่งที่คุณวงกลม)
    list_display = ('code', 'name', 'category', 'stock_qty', 'sell_price', 'show_image', 'is_active', 'print_button')
    
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code', 'barcode')
    list_editable = ('stock_qty', 'sell_price', 'is_active')

    # 🖼️ ฟังก์ชันแสดงรูปภาพจิ๋ว
    def show_image(self, obj):
        if obj.image:
            # แสดงรูปขนาด 50x50 pixel
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />', obj.image.url)
        return "-" # ถ้าไม่มีรูป ให้ขีดละไว้
    
    show_image.short_description = 'รูปสินค้า'

    # 🏷️ ฟังก์ชันปุ่มบาร์โค้ด (อันเดิม)
    def print_button(self, obj):
        url = reverse('print_barcode', args=[obj.id])
        return format_html('<a href="{}" target="_blank" class="button" style="background-color:#333; color:white; padding:5px 10px; border-radius:5px; text-decoration:none;">🏷️ Barcode</a>', url)
    
    print_button.short_description = 'สติ๊กเกอร์'