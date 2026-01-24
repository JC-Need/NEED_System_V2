from django.urls import path
from . import views
from . import views_employee
from . import views_network
from . import views_payroll

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
    path('analytics/', views.hr_executive_dashboard, name='hr_executive_dashboard'),

    # --- ระบบพนักงาน & โครงสร้างทีม (Modular Views) ---
    
    # ✅ แก้ไขตรงนี้: เปลี่ยนจาก views_employee เป็น views (เพื่อให้ใช้ฟอร์มใหม่ที่มีลายเซ็นต์)
    path('employee/add/', views.employee_add, name='employee_create'),
    
    path('network/tree/', views_network.network_tree, name='network_tree'),

    # --- API สำหรับปุ่ม Quick Add (+) ---
    path('api/create-position/', views_employee.api_create_position, name='api_create_position'),
    path('api/create-department/', views_employee.api_create_department, name='api_create_department'),

    # --- ระบบเงินเดือน (Payroll) ---
    path('payslips/', views_payroll.payslip_list, name='payslip_list'),
    path('payslip/<int:payslip_id>/', views_payroll.payslip_detail, name='payslip_detail'),
]