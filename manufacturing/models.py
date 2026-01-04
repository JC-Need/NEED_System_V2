from django.db import models
from django.utils import timezone
from inventory.models import Product
from hr.models import Employee

# ==========================================
# 1. สูตรการผลิต (Bill of Materials - BOM)
# ==========================================
class BOM(models.Model):
    # สูตรนี้สำหรับผลิตสินค้าอะไร?
    product = models.OneToOneField(Product, on_delete=models.CASCADE, verbose_name="สินค้าสำเร็จรูป (FG)")
    name = models.CharField(max_length=200, verbose_name="ชื่อสูตร (เช่น สูตรมาตรฐาน)")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    def __str__(self):
        return f"สูตรผลิต: {self.product.name}"

    class Meta:
        verbose_name = "1. สูตรการผลิต (BOM)"
        verbose_name_plural = "1. จัดการสูตรผลิต"

class BOMItem(models.Model):
    bom = models.ForeignKey(BOM, related_name='items', on_delete=models.CASCADE)
    raw_material = models.ForeignKey(Product, related_name='used_in_boms', on_delete=models.CASCADE, verbose_name="วัตถุดิบ (Raw Mat)")
    quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="จำนวนที่ใช้ (ต่อ 1 หน่วยผลิต)")
    
    def __str__(self):
        return f"{self.raw_material.name} ({self.quantity})"

# ==========================================
# 2. ใบสั่งผลิต (Production Order)
# ==========================================
class ProductionOrder(models.Model):
    STATUS_CHOICES = [
        ('PLANNED', 'วางแผน'),
        ('IN_PROGRESS', 'กำลังผลิต'),
        ('COMPLETED', 'ผลิตเสร็จแล้ว (เข้าสต็อก)'),
        ('CANCELLED', 'ยกเลิก')
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบสั่งผลิต")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่จะผลิต")
    quantity = models.IntegerField(default=1, verbose_name="จำนวนที่ผลิต")
    
    start_date = models.DateField(default=timezone.now, verbose_name="วันที่เริ่ม")
    finish_date = models.DateField(null=True, blank=True, verbose_name="วันที่เสร็จ")
    
    responsible_person = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ควบคุมการผลิต")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED', verbose_name="สถานะ")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    class Meta:
        verbose_name = "2. ใบสั่งผลิต"
        verbose_name_plural = "2. จัดการการผลิต"

    def __str__(self):
        return f"{self.code} - {self.product.name}"