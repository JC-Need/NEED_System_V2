from django.urls import path
from . import views

urlpatterns = [
    # ลิงก์พิมพ์บาร์โค้ด (รับ ID สินค้า)
    path('product/<int:product_id>/print_barcode/', views.print_barcode, name='print_barcode'),
]