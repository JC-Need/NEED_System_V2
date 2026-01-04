from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html # ✅ เพิ่มตัวนี้
from django.urls import reverse # ✅ เพิ่มตัวนี้
from .models import PurchaseOrder, PurchaseOrderItem
from accounting.models import Expense, ExpenseCategory

@admin.action(description='✅ ยืนยันรับของเข้าสต็อก (และลงบัญชี)')
def action_receive_stock(modeladmin, request, queryset):
    # (โค้ดฟังก์ชันรับของเดิม... ปล่อยไว้เหมือนเดิมครับ)
    try:
        cat = ExpenseCategory.objects.get(name__contains="ต้นทุน")
    except:
        cat, _ = ExpenseCategory.objects.get_or_create(name="ต้นทุนสินค้า (สั่งซื้อ)")

    for po in queryset:
        if po.status == 'RECEIVED': continue
        if po.status == 'CANCELLED': continue

        for item in po.items.all():
            if item.product:
                product = item.product
                product.stock_qty += item.quantity
                if item.unit_cost > 0: product.cost_price = item.unit_cost
                product.save()
        
        if po.total_amount > 0:
            Expense.objects.create(
                title=f"สั่งซื้อสินค้า PO {po.code}", amount=po.total_amount, category=cat,
                date=po.date, note=f"Auto from PO {po.code}"
            )
        po.status = 'RECEIVED'
        po.save()
        messages.success(request, f"✅ PO {po.code} รับของเรียบร้อย!")

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    # ✅ เพิ่ม 'print_button' เข้าไปใน list_display
    list_display = ('code', 'date', 'supplier', 'total_amount', 'status', 'print_button')
    list_filter = ('status', 'date', 'supplier')
    inlines = [PurchaseItemInline]
    actions = [action_receive_stock]

    # ✅ ฟังก์ชันสร้างปุ่มพิมพ์
    def print_button(self, obj):
        # สร้างลิงก์ไปที่ purchasing/po/{id}/print/
        url = reverse('po_print', args=[obj.id])
        return format_html(f'<a href="{url}" target="_blank" class="button" style="background-color:#fd7e14; color:white; padding:5px 10px; border-radius:5px; text-decoration:none;">🖨️ พิมพ์</a>')
    
    print_button.short_description = 'พิมพ์เอกสาร'