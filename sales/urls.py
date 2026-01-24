from django.urls import path
from . import views

urlpatterns = [
    # 1. หน้า Dashboard (Realtime)
    path('', views.sales_dashboard, name='sales_dashboard'),

    # 2. Sales Hub (ศูนย์รวมการขาย: เลือก POS หรือ Convert)
    path('hub/', views.sales_hub, name='sales_hub'), # ✅ หน้าใหม่!
    path('convert-quote/<int:qt_id>/', views.convert_quote_to_invoice, name='convert_quote_to_invoice'), # ✅ ฟังก์ชันแปลง

    # 3. ระบบ POS
    path('pos/', views.pos_home, name='pos_home'),
    path('pos/checkout/', views.pos_checkout, name='pos_checkout'),
    path('pos/print/<str:order_code>/', views.pos_print_slip, name='pos_print_slip'),

    # 4. ระบบใบเสนอราคา
    path('quotation/', views.quotation_list, name='quotation_list'),
    path('quotation/create/', views.quotation_create, name='quotation_create'),
    path('quotation/edit/<int:qt_id>/', views.quotation_edit, name='quotation_edit'),
    path('quotation/delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('quotation/print/<int:qt_id>/', views.quotation_print, name='quotation_print'),
    path('quotation/approve/<int:qt_id>/', views.quotation_approve, name='quotation_approve'),

    # 5. อื่นๆ
    path('api/customer-search/', views.api_search_customer, name='api_search_customer'),
    path('export/excel/', views.export_sales_excel, name='export_sales_excel'),
]