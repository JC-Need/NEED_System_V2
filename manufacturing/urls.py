from django.urls import path
from . import views

urlpatterns = [
    # ลิงก์สำหรับพิมพ์ใบสั่งผลิต (ของเดิม)
    path('production/<int:po_id>/print/', views.production_print, name='production_print'),

    # 🌟 เพิ่มใหม่: ลิงก์สำหรับหน้าคำนวณวัตถุดิบและการสร้างใบสั่งซื้อ (Auto PO)
    path('production/<int:pk>/detail/', views.production_detail, name='production_detail'),
    path('production/<int:pk>/generate-pos/', views.generate_pos_from_production, name='generate_pos_from_production'),
    path('prepare-purchase/', views.ppo_prepare, name='ppo_prepare'),
]