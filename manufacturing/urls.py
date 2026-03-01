from django.urls import path
from . import views

urlpatterns = [
    path('production/<int:po_id>/print/', views.production_print, name='production_print'),
    path('production/<int:pk>/detail/', views.production_detail, name='production_detail'),
    path('production/<int:pk>/generate-pos/', views.generate_pos_from_production, name='generate_pos_from_production'),
    path('prepare-purchase/', views.ppo_prepare, name='ppo_prepare'),
    
    # 🌟 เส้นทางสำหรับระบบสูตรผลิต (BOM) 🌟
    path('bom/', views.bom_list, name='bom_list'),            
    path('bom/create/', views.bom_create, name='bom_create'),
    path('bom/<int:pk>/', views.bom_detail, name='bom_detail'), 
    path('bom/<int:pk>/edit/', views.bom_edit, name='bom_edit'), # 🌟 เส้นทางใหม่สำหรับแก้ไข
]