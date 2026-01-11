from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- เชื่อมต่อแอปต่างๆ เข้ากับระบบหลัก ---
    path('', include('core.urls')),                # หน้าแรก
    path('hr/', include('hr.urls')),               # ระบบ HR
    path('sales/', include('sales.urls')),         # ระบบขาย
    path('inventory/', include('inventory.urls')), # ระบบคลังสินค้า
    
    # ⚠️ ปิดไว้ก่อนจนกว่าจะสร้างไฟล์ urls.py ในโฟลเดอร์เหล่านี้
    # path('purchasing/', include('purchasing.urls')),
    # path('manufacturing/', include('manufacturing.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)