from django.urls import path
from . import views

urlpatterns = [
    # 🌟 ระบบสั่งผลิต (Production Order) 🌟
    path('production/', views.production_list, name='production_list'),
    path('production/create/', views.production_create, name='production_create'),
    path('production/<int:pk>/process/', views.production_process, name='production_process'),

    # เส้นทางเดิม
    path('production/<int:po_id>/print/', views.production_print, name='production_print'),
    path('production/<int:pk>/detail/', views.production_detail, name='production_detail'),
    path('production/<int:pk>/generate-pos/', views.generate_pos_from_production, name='generate_pos_from_production'),
    path('prepare-purchase/', views.ppo_prepare, name='ppo_prepare'),

    # 🌟 เส้นทางสำหรับกระบวนการสั่งผลิต (หน้า Detail) 🌟
    path('production/<int:pk>/upload-blueprint/', views.upload_blueprint, name='upload_blueprint'),
    path('production/<int:pk>/load-bom/', views.load_standard_bom, name='load_standard_bom'),
    path('production/<int:pk>/start/', views.start_production, name='start_production'),
    
    # 🌟 เส้นทางสำหรับจัดการวัตถุดิบส่วนเพิ่ม 🌟
    path('production/<int:pk>/add-material/', views.add_additional_material, name='add_additional_material'),
    path('production/material/<int:pk>/delete/', views.delete_production_material, name='delete_production_material'),

    # ระบบสูตรผลิต (BOM)
    path('bom/', views.bom_list, name='bom_list'),
    path('bom/create/', views.bom_create, name='bom_create'),
    path('bom/<int:pk>/', views.bom_detail, name='bom_detail'),
    path('bom/<int:pk>/edit/', views.bom_edit, name='bom_edit'),
    
    # 🌟 เส้นทางสำหรับระบบกระดานติดตามงานและเพิ่มข้อมูลด่วน (AJAX) 🌟
    path('production/<int:pk>/update-board/', views.update_production_board, name='update_production_board'),
    path('ajax/add-branch/', views.ajax_add_branch, name='ajax_add_branch'),
    path('ajax/add-salesperson/', views.ajax_add_salesperson, name='ajax_add_salesperson'),
    path('ajax/add-prod-status/', views.ajax_add_prod_status, name='ajax_add_prod_status'),
    path('ajax/add-prod-team/', views.ajax_add_prod_team, name='ajax_add_prod_team'),
    path('ajax/add-delivery-status/', views.ajax_add_delivery_status, name='ajax_add_delivery_status'),
    path('ajax/add-transporter/', views.ajax_add_transporter, name='ajax_add_transporter'),
    
    # 🌟 เส้นทางใหม่: ดึงข้อมูล FG ตามหมวดหมู่ 🌟
    path('ajax/get-fg-by-category/', views.ajax_get_fg_by_category, name='ajax_get_fg_by_category'),
]