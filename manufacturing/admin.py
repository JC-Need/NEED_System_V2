from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    BOM, BOMItem, ProductionOrder, Branch, Salesperson,
    ProductionStatus, ProductionTeam, DeliveryStatus, Transporter
)

# ==========================================
# 🌟 เพิ่มเมนูจัดการ สาขา และ พนักงานขาย 🌟
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
# 🌟 เพิ่มเมนูจัดการสถานะหน้าตารางกระดานผลิต 🌟
# ==========================================

# 👇 ทำให้สามารถกรอกตัวเลขลำดับ (sequence) ได้ง่ายๆ จากหน้าแรก 👇
@admin.register(ProductionStatus)
class ProductionStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'sequence')
    list_editable = ('sequence',) # เปิดให้แก้เลข 1,2,3 ได้เลย
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
@admin.action(description='✅ ยืนยันผลิตเสร็จ (ตัดวัตถุดิบ + เพิ่มสินค้า)')
def action_complete_production(modeladmin, request, queryset):
    for po in queryset:
        if po.status == 'COMPLETED': continue
        try:
            bom = BOM.objects.get(product=po.product)
        except BOM.DoesNotExist:
            messages.error(request, f"❌ ไม่พบสูตร BOM ของ {po.product.name}")
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
            
        po.product.stock_qty += po.quantity
        po.product.save()

        po.status = 'COMPLETED'
        po.save()
        messages.success(request, f"✅ ผลิต {po.code} สำเร็จ!")

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