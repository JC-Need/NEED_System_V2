from django.contrib import admin
from .models import POSOrder, POSOrderItem, Quotation, QuotationItem, UpsaleCategory, UpsaleCatalog, QuotationUpsale, CustomerLead, Appointment

class POSItemInline(admin.TabularInline):
    model = POSOrderItem
    extra = 1 
    readonly_fields = ('total_price',)

@admin.register(POSOrder)
class POSOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'employee', 'customer', 'total_amount', 'status', 'is_commission_calculated', 'created_at')
    list_filter = ('status', 'is_commission_calculated', 'created_at', 'employee')
    search_fields = ('code', 'employee__first_name', 'customer__name')
    inlines = [POSItemInline]
    readonly_fields = ('is_commission_calculated',)

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

class QuotationUpsaleInline(admin.TabularInline):
    model = QuotationUpsale
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('code', 'date', 'customer', 'grand_total', 'status')
    inlines = [QuotationItemInline, QuotationUpsaleInline]
    list_filter = ('status', 'date')

# 🌟 จัดการหมวดหมู่ Upsale 🌟
@admin.register(UpsaleCategory)
class UpsaleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)

# 🌟 จัดการรายการ Upsale 🌟
@admin.register(UpsaleCatalog)
class UpsaleCatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'default_price', 'unit', 'is_active')
    search_fields = ('name',)
    list_filter = ('category', 'is_active')
    list_editable = ('default_price', 'is_active')

# ==========================================
# 🌟 ระบบ CRM และ นัดหมาย (แสดงผลใน Admin)
# ==========================================
@admin.register(CustomerLead)
class CustomerLeadAdmin(admin.ModelAdmin):
    list_display = ('code', 'customer_name', 'phone', 'channel', 'status', 'employee', 'created_at')
    list_filter = ('status', 'channel', 'employee')
    search_fields = ('code', 'customer_name', 'phone', 'requirements')
    ordering = ('-created_at',)
    list_per_page = 20

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('appointment_date', 'lead', 'appointment_type', 'status', 'employee')
    list_filter = ('status', 'appointment_type', 'employee')
    search_fields = ('lead__customer_name', 'lead__code', 'details')
    ordering = ('-appointment_date',)
    list_per_page = 20