from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_dashboard, name='inventory_dashboard'),
    
    # Stock Transactions
    path('in/', views.stock_in, name='stock_in'),
    path('out/', views.stock_out, name='stock_out'),
    
    # ✅ Product Management (เพิ่มใหม่)
    path('product/new/', views.product_create, name='product_create'),
    path('product/edit/<int:pk>/', views.product_update, name='product_update'),
    path('product/delete/<int:pk>/', views.product_delete, name='product_delete'),
    
    path('print-barcode/<int:product_id>/', views.print_barcode, name='print_barcode'),
]