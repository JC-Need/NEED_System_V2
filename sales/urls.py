from django.urls import path
from . import views

urlpatterns = [
    # 1. หน้า Dashboard
    path('', views.sales_dashboard, name='sales_dashboard'),

    # 2. ระบบ POS
    path('pos/', views.pos_home, name='pos_home'),
    path('pos/checkout/', views.pos_checkout, name='pos_checkout'),
    path('pos/print/<str:order_code>/', views.pos_print_slip, name='pos_print_slip'),

    # 3. ระบบใบเสนอราคา (Quotation)
    path('quotation/', views.quotation_list, name='quotation_list'),
    path('quotation/create/', views.quotation_create, name='quotation_create'),
    
    # ✅ บรรทัดนี้คือตัวแก้ Error ครับ! (เส้นทางไปหน้าแก้ไข)
    path('quotation/edit/<int:qt_id>/', views.quotation_edit, name='quotation_edit'),
    
    path('quotation/delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('quotation/print/<int:qt_id>/', views.quotation_print, name='quotation_print'),

    # 4. อื่นๆ
    path('export/excel/', views.export_sales_excel, name='export_sales_excel'),
]