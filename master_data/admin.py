from django.contrib import admin
from .models import (
    CompanyInfo, Department, Position, 
    Customer, Supplier, 
    Unit, ProductCategory, Product
)

# ตั้งค่าให้ CompanyInfo แก้ไขได้ง่ายๆ
@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('name_th', 'tax_id', 'phone')

# ตั้งค่า Customer ให้ค้นหาได้
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'phone', 'credit_term') # โชว์คอลัมน์เหล่านี้
    search_fields = ('code', 'name') # ช่องค้นหา พิมพ์ชื่อหรือรหัสก็เจอ

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'phone')
    search_fields = ('code', 'name')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'price_sell', 'is_active')
    list_filter = ('category', 'is_active') # ตัวกรองด้านขวา
    search_fields = ('code', 'name')

# Register ตัวอื่นๆ แบบปกติ
admin.site.register(Department)
admin.site.register(Position)
admin.site.register(Unit)
admin.site.register(ProductCategory)