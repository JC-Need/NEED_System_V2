from django.contrib import admin
from .models import CompanyInfo, Customer, Supplier

admin.site.register(CompanyInfo)
admin.site.register(Customer)
admin.site.register(Supplier)