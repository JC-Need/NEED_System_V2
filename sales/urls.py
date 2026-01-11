from django.urls import path
from . import views

urlpatterns = [
    path('', views.sales_dashboard, name='sales_dashboard'),
    path('pos/', views.pos_home, name='pos_home'),
    path('pos/checkout/', views.pos_checkout, name='pos_checkout'),
    path('pos/print/<str:order_code>/', views.pos_print_slip, name='pos_print_slip'),
    path('export/excel/', views.export_sales_excel, name='export_sales_excel'),

    path('quotation/', views.quotation_list, name='quotation_list'),
    path('quotation/create/', views.quotation_create, name='quotation_create'),
    path('quotation/<int:quote_id>/print/', views.quotation_print, name='quotation_print'),
]