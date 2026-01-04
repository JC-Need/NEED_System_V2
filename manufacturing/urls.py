from django.urls import path
from . import views

urlpatterns = [
    # ลิงก์สำหรับพิมพ์ใบสั่งผลิต
    path('production/<int:po_id>/print/', views.production_print, name='production_print'),
]