from django.urls import path
from . import views

urlpatterns = [
    # ตรวจสอบชื่อ 'purchasing_dashboard' ตรงนี้ครับ
    path('dashboard/', views.purchasing_dashboard, name='purchasing_dashboard'), 
    path('po/create/', views.po_create, name='po_create'),
    path('po/print/<int:po_id>/', views.po_print, name='po_print'),
]