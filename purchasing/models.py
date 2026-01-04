from django.db import models
from django.utils import timezone

# Import เพื่อนบ้าน
from master_data.models import Supplier
from inventory.models import Product
from hr.models import Employee

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'ร่าง (รออนุมัติ)'),
        ('ORDERED', 'สั่งซื้อแล้ว (รอของ)'),
        ('RECEIVED', 'ได้รับสินค้าแล้ว (เข้าสต็อก)'),
        ('CANCELLED', 'ยกเลิก')
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบสั่งซื้อ (PO)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ขาย (Supplier)")
    buyer = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้จัดซื้อ")
    
    date = models.DateField(default=timezone.now, verbose_name="วันที่สั่งซื้อ")
    expected_date = models.DateField(null=True, blank=True, verbose_name="กำหนดรับของ")
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดรวม")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="สถานะ")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "1. ใบสั่งซื้อ (PO)"
        verbose_name_plural = "1. จัดการใบสั่งซื้อ"

    def __str__(self):
        return f"{self.code} - {self.supplier}"

class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    
    quantity = models.IntegerField(default=1, verbose_name="จำนวนที่สั่ง")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ต้นทุนต่อหน่วย")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="รวมเป็นเงิน")

    def save(self, *args, **kwargs):
        # คำนวณราคารวมอัตโนมัติ
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"