from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Category, Product, InventoryDoc, StockMovement, FinishedGood, RawMaterial

# 1. หมวดหมู่
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

# ฟังก์ชันช่วยแสดงรูปภาพ (ใช้ร่วมกัน)
def show_image_preview(obj):
    if obj.image:
        return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
    return "-"
show_image_preview.short_description = 'รูป'

# ฟังก์ชันช่วยแสดงปุ่มบาร์โค้ด (ใช้ร่วมกัน)
def show_barcode_btn(obj):
    url = reverse('print_barcode', args=[obj.id])
    return format_html('<a href="{}" target="_blank" style="background:#333; color:fff; padding:3px 8px; border-radius:3px; text-decoration:none;">🏷️ Print</a>', url)
show_barcode_btn.short_description = 'Barcode'

# 2. สินค้ารวม (Product All) - เอาไว้ดูภาพรวม
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', show_image_preview, 'name', 'product_type', 'stock_qty', 'is_active')
    list_filter = ('product_type', 'category', 'is_active')
    search_fields = ('code', 'name')

# ✅ 2.1 เมนูสินค้าสำเร็จรูป (FG)
@admin.register(FinishedGood)
class FinishedGoodAdmin(admin.ModelAdmin):
    # เน้นโชว์ "ราคาขาย"
    list_display = ('code', show_image_preview, 'name', 'category', 'sell_price', 'stock_qty', 'is_active', show_barcode_btn)
    list_filter = ('category', 'is_active')
    search_fields = ('code', 'name')
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(product_type='FG')

    def save_model(self, request, obj, form, change):
        obj.product_type = 'FG' # บังคับเป็น FG
        super().save_model(request, obj, form, change)

# ✅ 2.2 เมนูวัตถุดิบ (RM)
@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    # เน้นโชว์ "ราคาทุน"
    list_display = ('code', show_image_preview, 'name', 'category', 'cost_price', 'stock_qty', 'is_active', show_barcode_btn)
    list_filter = ('category', 'is_active')
    search_fields = ('code', 'name')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(product_type='RM')

    def save_model(self, request, obj, form, change):
        obj.product_type = 'RM' # บังคับเป็น RM
        super().save_model(request, obj, form, change)

# 3. เอกสาร (Inventory Doc)
class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('product', 'quantity', 'movement_type')
    can_delete = False

@admin.register(InventoryDoc)
class InventoryDocAdmin(admin.ModelAdmin):
    list_display = ('doc_no', 'doc_type', 'created_at', 'created_by')
    list_filter = ('doc_type', 'created_at')
    search_fields = ('doc_no', 'reference')
    inlines = [StockMovementInline]