from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse

from inventory.models import Product # 🌟 [NEW] นำเข้าตาราง Product เพื่อใช้อ้างอิงสินค้าหลัก

from .models import (
    BOM, BOMItem, ProductionOrder, Branch, Salesperson,
    ProductionStatus, ProductionTeam, DeliveryStatus, Transporter,
    MfgBranch 
)

# ==========================================
# 🌟 เพิ่มเมนูจัดการ โรงงานผลิต
# ==========================================
@admin.register(MfgBranch)
class MfgBranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

# ==========================================
# 🌟 เพิ่มเมนูจัดการ สาขาหน้าร้าน และ พนักงานขาย
# ==========================================
@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'branch')
    list_filter = ('branch',)
    search_fields = ('name',)

# ==========================================
# 🌟 เพิ่มเมนูจัดการสถานะหน้าตารางกระดานผลิต
# ==========================================
@admin.register(ProductionStatus)
class ProductionStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'sequence')
    list_editable = ('sequence',) 
    ordering = ('sequence', 'id')

admin.site.register(ProductionTeam)
admin.site.register(DeliveryStatus)
admin.site.register(Transporter)

# ==========================================
# ส่วน BOMAdmin
# ==========================================
class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1
    fk_name = 'bom'

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('product', 'name')
    inlines = [BOMItemInline]
    search_fields = ('product__name',)

# ==========================================
# ส่วน Action และ ProductionOrder 
# ==========================================
@admin.action(description='✅ ยืนยันผลิตเสร็จ (ตัดวัตถุดิบ + เพิ่มสต็อกสินค้าหลัก)')
def action_complete_production(modeladmin, request, queryset):
    for po in queryset:
        if po.status == 'COMPLETED': continue
        
        # 🌟 [FIX] ตรวจจับและดึง "สินค้าหลัก" ในกรณีที่เป็นสินค้ารหัสชั่วคราว (-JOB)
        target_product = po.product
        if target_product and '-JOB' in target_product.code:
            base_code = target_product.code.split('-JOB')[0]
            master_product = Product.objects.filter(code=base_code).first()
            if master_product:
                target_product = master_product

        try:
            bom = BOM.objects.get(product=target_product)
        except BOM.DoesNotExist:
            messages.error(request, f"❌ ไม่พบสูตร BOM ของ {target_product.name}")
            continue

        can_produce = True
        for item in bom.items.all():
            req = item.quantity * po.quantity
            if item.raw_material.stock_qty < req:
                messages.error(request, f"⚠️ วัตถุดิบ {item.raw_material.name} ไม่พอ")
                can_produce = False
                break
        if not can_produce: continue

        for item in bom.items.all():
            req = item.quantity * po.quantity
            item.raw_material.stock_qty -= req
            item.raw_material.save()
            
        # 🌟 [FIX] เพิ่มสต็อกเข้าที่สินค้าหลักเสมอ
        target_product.stock_qty += po.quantity
        target_product.save()

        po.status = 'COMPLETED'
        po.save()
        messages.success(request, f"✅ ผลิต {po.code} สำเร็จ! (เพิ่มสต็อกให้ {target_product.code} แล้ว)")

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'product', 'quantity', 'status', 'start_date', 'branch', 'salesperson', 'print_button')
    list_filter = ('status', 'start_date', 'branch')
    search_fields = ('code', 'product__name', 'customer_name')
    actions = [action_complete_production]

    def print_button(self, obj):
        url = reverse('production_print', args=[obj.id])
        return format_html(f'<a href="{url}" target="_blank" class="button" style="background-color:#6f42c1; color:white; padding:5px 10px; border-radius:5px; text-decoration:none;">🖨️ ใบสั่งผลิต</a>')
    print_button.short_description = 'เอกสาร'