from django.contrib import admin
from .models import POSOrder, POSOrderItem, Quotation, QuotationItem

# --- จัดการ POS ---
class POSItemInline(admin.TabularInline):
    model = POSOrderItem
    extra = 0
    readonly_fields = ('total_price',)

@admin.register(POSOrder)
class POSOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'created_at', 'employee', 'total_amount', 'payment_method')
    inlines = [POSItemInline]
    list_filter = ('created_at', 'payment_method')

# --- จัดการ Quotation ---
class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('code', 'date', 'customer', 'grand_total', 'status')
    inlines = [QuotationItemInline]
    list_filter = ('status', 'date')