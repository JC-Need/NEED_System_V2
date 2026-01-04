from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html # ✅
from django.urls import reverse # ✅
from .models import BOM, BOMItem, ProductionOrder

# ... (ส่วน BOMAdmin ด้านบน ปล่อยไว้เหมือนเดิม) ...
class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1
    fk_name = 'bom'

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('product', 'name')
    inlines = [BOMItemInline]
    search_fields = ('product__name',)

# ... (ส่วน Action เดิม ปล่อยไว้เหมือนเดิม) ...
@admin.action(description='✅ ยืนยันผลิตเสร็จ (ตัดวัตถุดิบ + เพิ่มสินค้า)')
def action_complete_production(modeladmin, request, queryset):
    # (โค้ดเดิมซ่อนไว้เพื่อความสั้น... แต่ในไฟล์จริงต้องมีนะครับ)
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
    # ✅ เพิ่ม 'print_button'
    list_display = ('code', 'product', 'quantity', 'status', 'start_date', 'print_button')
    list_filter = ('status', 'start_date')
    actions = [action_complete_production]

    # ✅ ฟังก์ชันสร้างปุ่มพิมพ์ (สีม่วง)
    def print_button(self, obj):
        url = reverse('production_print', args=[obj.id])
        return format_html(f'<a href="{url}" target="_blank" class="button" style="background-color:#6f42c1; color:white; padding:5px 10px; border-radius:5px; text-decoration:none;">🖨️ ใบสั่งผลิต</a>')
    
    print_button.short_description = 'เอกสาร'