from django.urls import path
from . import views

urlpatterns = [
    # ✅ หน้า Dashboard หลัก (รวม RM และ FG ที่เราทำใหม่)
    path('', views.inventory_dashboard, name='inventory_dashboard'),

    # ❌ ลบบรรทัด 'warehouse/' ที่ Error ทิ้งไปครับ
    # เพราะเราใช้ path '' ด้านบนเป็น Dashboard ตัวใหม่แล้ว

    # การเคลื่อนไหวสต็อก (รับเข้า / เบิกออก)
    path('stock/in/', views.stock_in, name='stock_in'),
    path('stock/out/', views.stock_out, name='stock_out'),

    # จัดการสินค้า (เพิ่ม / แก้ไข / ลบ / พิมพ์บาร์โค้ด)
    path('product/new/', views.product_create, name='product_create'),
    path('product/edit/<int:pk>/', views.product_update, name='product_update'),
    path('product/delete/<int:pk>/', views.product_delete, name='product_delete'),
    path('print-barcode/<int:product_id>/', views.print_barcode, name='print_barcode'),
    path('print-doc/<str:doc_no>/', views.print_document, name='print_document'),
]