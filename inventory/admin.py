from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

# 🌟 [UPDATE] เพิ่ม RawMaterialCategory เข้ามา
from .models import Category, RawMaterialCategory, Product, InventoryDoc, StockMovement, FinishedGood, RawMaterial

# 1. หมวดหมู่
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

# 🌟 [NEW] 1.1 หมวดหมู่วัตถุดิบ (แผนกต่างๆ)
@admin.register(RawMaterialCategory)
class RawMaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

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
    # 🌟 [UPDATE] แทรก 'unit' เข้ามาแสดงผล
    list_display = ('code', show_image_preview, 'name', 'product_type', 'stock_qty', 'unit', 'is_active')
    list_filter = ('product_type', 'category', 'is_active')
    search_fields = ('code', 'name')

# ✅ 2.1 เมนูสินค้าสำเร็จรูป (FG)
@admin.register(FinishedGood)
class FinishedGoodAdmin(admin.ModelAdmin):
    # 🌟 [UPDATE] แทรก 'unit' เข้ามาแสดงผล
    list_display = ('code', show_image_preview, 'name', 'category', 'sell_price', 'stock_qty', 'unit', 'is_active', show_barcode_btn)
    list_filter = ('category', 'is_active')
    search_fields = ('code', 'name')
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(product_type='FG')

    def save_model(self, request, obj, form, change):
        obj.product_type = 'FG' # บังคับเป็น FG
        super().save_model(request, obj, form, change)

    # 🌟 [NEW] ระบบดักจับและจำกัดสิทธิ์สำหรับฝ่ายขาย (Read-Only) 🌟
    def is_sales_user(self, request):
        if request.user.is_superuser:
            return False # Admin ผ่านได้ปกติ
        # เช็คว่าล็อกอินมีข้อมูล Employee ผูกอยู่ และอยู่แผนกขายหรือไม่
        if hasattr(request.user, 'employee') and request.user.employee:
            dept_name = request.user.employee.department.name if request.user.employee.department else ''
            if 'ขาย' in dept_name or 'Sales' in dept_name:
                return True
        return False

    def has_view_permission(self, request, obj=None):
        return True # ให้ทุกคน (รวมถึงเซลส์) มองเห็นและกดเข้าไปดูรายละเอียดได้

    def has_add_permission(self, request):
        if self.is_sales_user(request):
            return False # ห้ามเซลส์เพิ่มสินค้าใหม่
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if self.is_sales_user(request):
            return False # ห้ามเซลส์แก้ไขข้อมูล (ระบบจะเปลี่ยนหน้าจอเป็น Read-Only อัตโนมัติ)
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self.is_sales_user(request):
            return False # ห้ามเซลส์ลบสินค้า
        return super().has_delete_permission(request, obj)

# ✅ 2.2 เมนูวัตถุดิบ (RM)
@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    # 🌟 [UPDATE] แทรก 'unit' เข้ามาแสดงผล
    list_display = ('code', show_image_preview, 'name', 'rm_category', 'cost_price', 'stock_qty', 'unit', 'supplier', 'is_active', show_barcode_btn)
    list_filter = ('rm_category', 'supplier', 'is_active')
    search_fields = ('code', 'name', 'supplier__name', 'supplier__code')

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