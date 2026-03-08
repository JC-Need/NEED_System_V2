from django.urls import path
from . import views

urlpatterns = [
    # หน้าหลัก Dashboard บัญชี
    path('dashboard/', views.accounting_dashboard, name='accounting_dashboard'),
]