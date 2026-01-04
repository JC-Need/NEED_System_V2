from django.urls import path
from . import views

urlpatterns = [
    # ลิงก์สำหรับพิมพ์ใบสั่งซื้อ (รับ ID ของ PO)
    path('po/<int:po_id>/print/', views.po_print, name='po_print'),
]