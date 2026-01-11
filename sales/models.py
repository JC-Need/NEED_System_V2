from django.db import models
from django.utils import timezone
from decimal import Decimal

# Import เพื่อนบ้าน
from master_data.models import Customer
from hr.models import Employee, CommissionLog
from inventory.models import Product

class POSOrder(models.Model):
    # สถานะบิล (Trigger สำคัญ)
    STATUS_CHOICES = [
        ('PENDING', 'รอชำระเงิน'),
        ('PAID', 'ชำระเงินแล้ว'),
        ('CANCELLED', 'ยกเลิก'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสร็จ")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="พนักงานขาย")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ลูกค้า")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดรวม")
    received_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รับเงินมา")
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินทอน")
    payment_method = models.CharField(max_length=50, choices=[('CASH','เงินสด'), ('QR','โอน/สแกน')], default='CASH', verbose_name="วิธีชำระ")

    # ✅ สองฟิลด์นี้แหละที่หายไป ทำให้เกิด Error!
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PAID', verbose_name="สถานะ")
    is_commission_calculated = models.BooleanField(default=False, verbose_name="คำนวณคอมฯแล้ว")

    created_at = models.DateTimeField(default=timezone.now, verbose_name="เวลาที่ขาย")

    class Meta:
        verbose_name = "บิลขายหน้าร้าน (POS)"
        verbose_name_plural = "ประวัติการขาย POS"

    def __str__(self):
        return f"{self.code} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # ระบบคำนวณคอมมิชชั่น
        if self.status == 'PAID' and not self.is_commission_calculated and self.employee:
            self.calculate_commission()

    def calculate_commission(self):
        print(f"💰 เริ่มคำนวณคอมมิชชั่นสำหรับบิล: {self.code}")
        seller = self.employee

        # 1. จ่ายคนขาย
        rate = seller.commission_rate
        if rate > 0:
            amt = self.total_amount * (rate / 100)
            CommissionLog.objects.create(recipient=seller, source_employee=seller, level=0, amount=amt, sale_ref_id=self.code)

        # 2. จ่ายแม่ทีม (3 ชั้น)
        current_upline = seller.introducer
        level = 1
        override_rates = {1: 5.0, 2: 2.0, 3: 1.0}

        while current_upline and level <= 3:
            override_percent = override_rates.get(level, 0)
            if override_percent > 0:
                override_amt = self.total_amount * (Decimal(override_percent) / 100)
                CommissionLog.objects.create(recipient=current_upline, source_employee=seller, level=level, amount=override_amt, sale_ref_id=self.code)
            current_upline = current_upline.introducer
            level += 1

        POSOrder.objects.filter(id=self.id).update(is_commission_calculated=True)

class POSOrderItem(models.Model):
    order = models.ForeignKey(POSOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")

    # ✅ กู้คืนบรรทัดนี้กลับมาครับ!
    product_name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า (ณ ตอนขาย)", null=True, blank=True)

    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อชิ้น")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคารวม")

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price
        # ถ้าไม่มีชื่อสินค้า ให้ดึงจาก Product Master
        if not self.product_name and self.product:
            self.product_name = self.product.name
        super().save(*args, **kwargs)

class Quotation(models.Model): # (ติดมาด้วยเผื่อไว้ครับ)
    code = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    date = models.DateField(default=timezone.now)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='DRAFT')

class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)