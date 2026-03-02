from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.purchasing_dashboard, name='purchasing_dashboard'), 
    
    # 🌟 เส้นทางใหม่: หน้ารวมใบสั่งซื้อทั้งหมด 🌟
    path('po/list/', views.po_list, name='po_list'),
    
    path('po/create/', views.po_create, name='po_create'),
    path('po/edit/<int:po_id>/', views.po_edit, name='po_edit'),
    path('po/print/<int:po_id>/', views.po_print, name='po_print'),
    path('po/payment/<int:po_id>/', views.po_payment, name='po_payment'),
    
    path('ppo/list/', views.ppo_list, name='ppo_list'),
    path('ppo/<int:pk>/', views.ppo_detail, name='ppo_detail'),
]