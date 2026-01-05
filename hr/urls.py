from django.urls import path
from . import views

urlpatterns = [
    # ... path อื่นๆ ...
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
]