from django.db import models
from master_data.models import Supplier # ดึงข้อมูลซัพพลายเออร์จากถังกลาง

# ==========================================
# 1. หมวดหมู่สินค้า (Category)
# ==========================================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อหมวดหมู่")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "1. หมวดหมู่สินค้า"
        verbose_name_plural = "1. จัดการหมวดหมู่ (Categories)"

# ==========================================
# 2. สินค้า (Product)
# ==========================================
class Product(models.Model):
    # ข้อมูลพื้นฐาน
    code = models.CharField(max_length=50, unique=True, verbose_name="รหัสสินค้า/SKU")
    barcode = models.CharField(max_length=50, blank=True, null=True, verbose_name="บาร์โค้ด")
    name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, verbose_name="หมวดหมู่")
    
    # ราคาและต้นทุน
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาทุน")
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาขาย")
    
    # สต็อก
    stock_qty = models.IntegerField(default=0, verbose_name="จำนวนคงเหลือ")
    min_level = models.IntegerField(default=5, verbose_name="จุดสั่งซื้อ (Low Stock)")
    
    # อื่นๆ
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ซัพพลายเออร์หลัก")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="รูปสินค้า")
    is_active = models.BooleanField(default=True, verbose_name="เปิดขาย")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.stock_qty})"

    class Meta:
        verbose_name = "2. รายการสินค้า"
        verbose_name_plural = "2. จัดการสินค้า (Products)"