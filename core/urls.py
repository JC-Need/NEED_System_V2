from django.urls import path
from . import views

urlpatterns = [
    # ตั้งชื่อว่า 'dashboard' ให้ตรงกับที่ตั้งไว้ใน LOGIN_REDIRECT_URL
    path('', views.dashboard, name='dashboard'),
]