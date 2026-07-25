from django.urls import path
from . import views

urlpatterns = [
    # 🌟 หน้า Dashboard หลักของแผนก Center
    path('dashboard/', views.center_dashboard, name='solar_center_dashboard'),
    
    # 🌟 ระบบจัดการงานติดตั้ง
    path('create-quick-job/', views.solar_job_create, name='solar_job_create'),
    path('manage/<int:job_id>/', views.solar_job_manage, name='solar_job_manage'),
    
    # 🌟 ระบบตั้งเบิกค่าใช้จ่าย
    path('expenses/', views.expense_list, name='solar_expense_list'),
    path('expenses/create/', views.expense_create, name='solar_expense_create'),
    path('expenses/approve/<int:expense_id>/', views.expense_approve, name='solar_expense_approve'),
]