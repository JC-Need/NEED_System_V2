from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- เชื่อมต่อแอปต่างๆ เข้ากับระบบหลัก ---
    path('', include('core.urls')),                # หน้าแรกและระบบ Login กลาง
    path('hr/', include('hr.urls')),               # 👈 เพิ่มบรรทัดนี้: ระบบ HR (Dashboard, ใบลา, เงินเดือน)
    path('sales/', include('sales.urls')),         # ระบบขาย
    path('purchasing/', include('purchasing.urls')), # ระบบจัดซื้อ
    path('manufacturing/', include('manufacturing.urls')), # ระบบผลิต
    path('inventory/', include('inventory.urls')), # ระบบคลังสินค้า
]

# สำหรับแสดงรูปภาพในโหมด Debug (ตอนพัฒนาบนเครื่องตัวเอง)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)