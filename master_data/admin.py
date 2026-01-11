from django.contrib import admin
# ✅ Import แค่ 3 ตัวที่เราเก็บไว้จริง
from .models import CompanyInfo, Customer, Supplier

# 1. ข้อมูลบริษัท
@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('name_th', 'tax_id', 'branch')

# 2. ลูกค้า
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'phone', 'points')
    search_fields = ('code', 'name', 'phone')

# 3. ซัพพลายเออร์
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'contact_name', 'phone')
    search_fields = ('code', 'name')