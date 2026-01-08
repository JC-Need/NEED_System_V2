from django.urls import path
from . import views
from . import views_employee
from . import views_network

urlpatterns = [
    # ... path อื่นๆ ...
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('check-in/', views.check_in, name='check_in'),
    path('check-out/', views.check_out, name='check_out'),
    path('leave/create/', views.leave_create, name='leave_create'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/approve/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('manager/reject/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('admin-dashboard/', views.hr_executive_dashboard, name='hr_executive_dashboard'),
    path('manager/reject/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('analytics/', views.hr_executive_dashboard, name='hr_executive_dashboard'),
    path('employee/add/', views_employee.employee_create, name='employee_create'),
    path('network/tree/', views_network.network_tree, name='network_tree'),
]