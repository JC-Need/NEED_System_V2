from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- เชื่อมต่อแอปต่างๆ เข้ากับระบบหลัก ---
    path('', include('core.urls')),                # หน้าแรก (Dashboard)
    path('hr/', include('hr.urls')),               # ระบบ HR
    path('sales/', include('sales.urls')),         # ระบบขาย
    path('inventory/', include('inventory.urls')), # ระบบคลังสินค้า
    
    # ✅ เพิ่มบรรทัดนี้: เชื่อมต่อระบบข้อมูลลูกค้า (Master Data)
    path('master_data/', include('master_data.urls')), 
    
    # ระบบอื่นๆ (รอสร้างในอนาคต)
    # path('purchasing/', include('purchasing.urls')),
    # path('manufacturing/', include('manufacturing.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)