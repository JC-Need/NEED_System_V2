from django.contrib import admin
from .models import POSOrder, POSOrderItem, Quotation, QuotationItem, UpsaleCatalog, QuotationUpsale

# ==========================================
# 1. จัดการ POS (ขายหน้าร้าน)
# ==========================================
class POSItemInline(admin.TabularInline):
    model = POSOrderItem
    extra = 1 # แสดงแถวว่าง 1 แถวให้กรอกง่ายๆ
    readonly_fields = ('total_price',) # ราคารวมให้ระบบคิดเอง ห้ามแก้

@admin.register(POSOrder)
class POSOrderAdmin(admin.ModelAdmin):
    # ✅ เพิ่ม 'status' และ 'is_commission_calculated' เพื่อให้ดูผลง่ายๆ
    list_display = ('code', 'employee', 'customer', 'total_amount', 'status', 'is_commission_calculated', 'created_at')
    
    # ตัวกรองด้านขวา
    list_filter = ('status', 'is_commission_calculated', 'created_at', 'employee')
    
    # ช่องค้นหา
    search_fields = ('code', 'employee__first_name', 'customer__name')
    
    # ใส่ตารางสินค้าเข้าไปในหน้าบิลเลย
    inlines = [POSItemInline]
    
    # ล็อคช่องนี้ไว้ ไม่ให้คนไปแอบติ๊กเล่น (ให้ระบบติ๊กเองตอนจ่ายเงิน)
    readonly_fields = ('is_commission_calculated',)

# ==========================================
# 2. จัดการ Quotation (ใบเสนอราคา)
# ==========================================
class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

# 🌟 [เพิ่มใหม่] จัดการรายการสั่งเพิ่ม (Upsale) ในหน้าใบเสนอราคา 🌟
class QuotationUpsaleInline(admin.TabularInline):
    model = QuotationUpsale
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('code', 'date', 'customer', 'grand_total', 'status')
    # ✅ นำตารางของสั่งเพิ่ม (Upsale) มาโชว์ในหน้าแอดมินด้วย
    inlines = [QuotationItemInline, QuotationUpsaleInline]
    list_filter = ('status', 'date')

# ==========================================
# 🌟 3. [เพิ่มใหม่] จัดการแคตตาล็อก Upsale (Master Data) 🌟
# ==========================================
@admin.register(UpsaleCatalog)
class UpsaleCatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_price', 'unit', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)
    # ✅ ให้แอดมินสามารถแก้ราคา หรือกดเปิด/ปิดใช้งาน จากหน้าตารางรวมได้เลยเพื่อความรวดเร็ว
    list_editable = ('default_price', 'is_active')