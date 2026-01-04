from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('core.urls')),
    path('sales/', include('sales.urls')),
    path('purchasing/', include('purchasing.urls')),
    path('manufacturing/', include('manufacturing.urls')),
    
    # ✅ เพิ่มบรรทัดนี้: คลังสินค้า (สำหรับพิมพ์บาร์โค้ด)
    path('inventory/', include('inventory.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)