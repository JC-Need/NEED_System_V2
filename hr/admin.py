from django.contrib import admin
from .models import Department, Position, Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'first_name', 'position', 'phone', 'is_active')
    search_fields = ('first_name', 'nickname', 'employee_id')
    list_filter = ('position', 'is_active')

admin.site.register(Department)
admin.site.register(Position)