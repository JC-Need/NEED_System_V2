from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from master_data.models import Supplier # อ้างอิงจากไฟล์เดิมที่มี

# ==========================================
# 1. หมวดหมู่สินค้า (Category)
# ==========================================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อหมวดหมู่")
    
    def __str__(self): return self.name
    
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
    
    # สต็อก (สำคัญ!)
    stock_qty = models.IntegerField(default=0, verbose_name="จำนวนคงเหลือ")
    min_level = models.IntegerField(default=5, verbose_name="จุดสั่งซื้อ (Low Stock)")
    
    # อื่นๆ
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ซัพพลายเออร์หลัก")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="รูปสินค้า")
    is_active = models.BooleanField(default=True, verbose_name="เปิดขาย")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (คงเหลือ: {self.stock_qty})"

    class Meta:
        verbose_name = "2. รายการสินค้า"
        verbose_name_plural = "2. จัดการสินค้า (Products)"

# ==========================================
# 3. บันทึกการเคลื่อนไหวสต็อก (Stock Movement) - ✅ ส่วนที่เพิ่มใหม่
# ==========================================
class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'รับเข้า (ซื้อ/ผลิตเสร็จ)'),
        ('OUT', 'เบิกออก (ขาย/เสียหาย)'),
        ('PRODUCTION', 'เบิกไปผลิต'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, verbose_name="ประเภทรายการ")
    quantity = models.IntegerField(verbose_name="จำนวน")
    
    reference_doc = models.CharField(max_length=50, blank=True, verbose_name="อ้างอิงเอกสาร (PO/SO)")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ทำรายการ")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="วันที่ทำรายการ")

    def save(self, *args, **kwargs):
        # ✅ Logic อัตโนมัติ: เมื่อบันทึก Transaction -> ให้ไปตัดยอดที่ Product ทันที
        if not self.pk: # ทำเฉพาะตอนสร้างใหม่ (กันยอดเพี้ยนตอนแก้ไข)
            if self.movement_type == 'IN':
                self.product.stock_qty += self.quantity
            else: # OUT หรือ PRODUCTION
                self.product.stock_qty -= self.quantity
            
            self.product.save() # บันทึกยอดคงเหลือใหม่ลงสินค้า
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name}"

    class Meta:
        verbose_name = "3. ประวัติสต็อก"
        verbose_name_plural = "3. ประวัติการเคลื่อนไหว (Stock Movements)"