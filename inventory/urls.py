from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_dashboard, name='inventory_dashboard'),
    
    # ✅ เปลี่ยนใหม่: แยกหน้า In และ Out
    path('documents/in/', views.document_list_in, name='document_list_in'),   # หน้ารายการรับเข้า
    path('documents/out/', views.document_list_out, name='document_list_out'), # หน้ารายการเบิกออก

    path('stock/in/', views.stock_in, name='stock_in'),   # (ฟอร์มบันทึก - ยังเก็บไว้)
    path('stock/out/', views.stock_out, name='stock_out'), # (ฟอร์มบันทึก - ยังเก็บไว้)
    
    path('product/new/', views.product_create, name='product_create'),
    path('product/edit/<int:pk>/', views.product_update, name='product_update'),
    path('product/delete/<int:pk>/', views.product_delete, name='product_delete'),
    path('print-barcode/<int:product_id>/', views.print_barcode, name='print_barcode'),
    path('print-doc/<str:doc_no>/', views.print_document, name='print_document'),
]