from django.urls import path
from . import views
from . import views_employee
from . import views_network
from . import views_payroll  # ✅ 1. เพิ่มบรรทัดนี้: เพื่อดึงระบบเงินเดือนมาใช้

urlpatterns = [
    # --- ระบบหลัก (Core HR) ---
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('check-in/', views.check_in, name='check_in'),
    path('check-out/', views.check_out, name='check_out'),
    path('leave/create/', views.leave_create, name='leave_create'),

    # --- ระบบผู้จัดการ (Manager) ---
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/approve/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('manager/reject/<int:leave_id>/', views.reject_leave, name='reject_leave'),

    # --- ระบบผู้บริหาร (Executive Analytics) ---
    path('analytics/', views.hr_executive_dashboard, name='hr_executive_dashboard'), # ใช้ path นี้เป็นหลัก
    # path('admin-dashboard/', ... ) # อันเก่าถ้าไม่ได้ใช้แล้ว ลบออกได้ครับ เพื่อไม่ให้ซ้ำซ้อน

    # --- ระบบพนักงาน & โครงสร้างทีม (Modular Views) ---
    path('employee/add/', views_employee.employee_create, name='employee_create'),
    path('network/tree/', views_network.network_tree, name='network_tree'),

    # --- API สำหรับปุ่ม Quick Add (+) ---
    path('api/create-position/', views_employee.api_create_position, name='api_create_position'),
    path('api/create-department/', views_employee.api_create_department, name='api_create_department'),

    # --- ✅ 2. ระบบเงินเดือน (Payroll) เพิ่มใหม่ ---
    path('payslips/', views_payroll.payslip_list, name='payslip_list'),
    path('payslip/<int:payslip_id>/', views_payroll.payslip_detail, name='payslip_detail'),
]