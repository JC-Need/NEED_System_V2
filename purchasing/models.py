from django.db import models
from django.utils import timezone
from master_data.models import Supplier
from inventory.models import Product
from hr.models import Employee

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'ร่าง (รออนุมัติ)'),
        ('APPROVED', 'อนุมัติแล้ว (ดำเนินการสั่งซื้อ)'),
        ('CANCELLED', 'ยกเลิก')
    ]

    PAYMENT_STATUS = [('PENDING', 'รอชำระเงิน'), ('DEPOSIT', 'จ่ายมัดจำแล้ว'), ('PAID', 'ชำระครบแล้ว')]
    DELIVERY_STATUS = [('PENDING', 'รอดำเนินการจัดส่ง'), ('SHIPPED', 'ร้านค้าส่งของแล้ว')]
    RECEIPT_STATUS = [('PENDING', 'รอรับเข้าคลัง'), ('PARTIAL', 'รับของบางส่วน'), ('COMPLETED', 'รับของครบถ้วน')]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบสั่งซื้อ (PO)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ขาย (Supplier)")
    buyer = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้จัดซื้อ")
    
    # ★ เพิ่มการอ้างอิงใบเตรียมการสั่งซื้อ (PPO) ★
    ppo_ref = models.CharField(max_length=20, blank=True, null=True, verbose_name="อ้างอิงใบเตรียมการสั่งซื้อ (PPO)")
    
    production_ref = models.ForeignKey('manufacturing.ProductionOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_pos', verbose_name="อ้างอิงใบสั่งผลิต")
    date = models.DateField(default=timezone.now, verbose_name="วันที่สั่งซื้อ")
    expected_date = models.DateField(null=True, blank=True, verbose_name="กำหนดรับของ")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดรวม")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="สถานะเอกสาร")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING', verbose_name="สถานะชำระเงิน")
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='PENDING', verbose_name="สถานะจัดส่ง")
    receipt_status = models.CharField(max_length=20, choices=RECEIPT_STATUS, default='PENDING', verbose_name="สถานะรับของเข้าคลัง")
    
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "1. ใบสั่งซื้อ (PO)"
        verbose_name_plural = "1. จัดการใบสั่งซื้อ"

    def __str__(self):
        return f"{self.code} - {self.supplier}"

class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า/วัตถุดิบ")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="จำนวนที่สั่ง")
    received_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="จำนวนที่รับเข้าคลังแล้ว")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ต้นทุนต่อหน่วย")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="รวมเป็นเงิน")

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name if self.product else 'Unknown'} ({self.quantity})"