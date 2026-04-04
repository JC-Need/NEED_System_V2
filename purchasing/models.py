from django.db import models
from django.utils import timezone
from master_data.models import Supplier
from inventory.models import Product
from hr.models import Employee
import datetime
from PIL import Image

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

    def save(self, *args, **kwargs):
        if self.receipt_status == 'COMPLETED' and self.delivery_status == 'PENDING':
            self.delivery_status = 'SHIPPED'
        super().save(*args, **kwargs)

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

class PurchaseOrderPayment(models.Model):
    po = models.ForeignKey(PurchaseOrder, related_name='payments', on_delete=models.CASCADE)
    payment_date = models.DateField(default=timezone.now, verbose_name="วันที่ชำระเงิน")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ยอดชำระ")
    payment_method = models.CharField(max_length=50, default="โอนเงินผ่านธนาคาร", verbose_name="ช่องทางการชำระ")
    reference_no = models.CharField(max_length=100, blank=True, verbose_name="เลขอ้างอิง / สลิป")
    
    # 🌟 [NEW] เพิ่มช่องเก็บสลิปโอนเงิน 🌟
    slip_image = models.ImageField(upload_to='po_payment_slips/%Y/%m/', null=True, blank=True, verbose_name="สลิปโอนเงิน")
    
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ประวัติการชำระเงิน PO"
        verbose_name_plural = "ประวัติการชำระเงิน PO"

    def __str__(self):
        return f"{self.po.code} - {self.amount}"

    # 🌟 [NEW] ย่อรูปลงอัตโนมัติ ไม่ให้หนักเซิร์ฟเวอร์ 🌟
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.slip_image:
            try:
                img = Image.open(self.slip_image.path)
                if img.height > 800 or img.width > 800:
                    img.thumbnail((800, 800))
                    img.save(self.slip_image.path, quality=85, optimize=True)
            except Exception: pass

class PurchasePreparation(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเตรียมสั่งซื้อ (PPO)")
    production_orders = models.ManyToManyField('manufacturing.ProductionOrder', related_name='ppos', verbose_name="อ้างอิงใบสั่งผลิต (JOB)")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้จัดทำ")

    def save(self, *args, **kwargs):
        if not self.code:
            today = datetime.date.today()
            thai_year = (today.year + 543) % 100
            prefix = f"PPO{thai_year:02d}{today.strftime('%m')}"

            last_ppo = PurchasePreparation.objects.filter(code__startswith=prefix).order_by('code').last()
            if last_ppo:
                try: seq = int(last_ppo.code.replace(prefix, '')) + 1
                except: seq = 1
            else:
                seq = 1
            self.code = f"{prefix}{seq:03d}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "ใบเตรียมสั่งซื้อ (PPO)"
        verbose_name_plural = "ใบเตรียมสั่งซื้อ (PPO)"

    def __str__(self):
        return self.code

class OverseasPO(models.Model):
    supplier_name = models.CharField(max_length=200, verbose_name="ชื่อร้านค้า (Supplier)")
    pi_number = models.CharField(max_length=50, verbose_name="เลขที่ PI")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดสั่งซื้อรวม")

    is_fully_paid = models.BooleanField(default=False, verbose_name="ชำระครบแล้ว")
    deposit_date = models.DateField(null=True, blank=True, verbose_name="วันที่ชำระมัดจำ")
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดมัดจำ")
    balance_date = models.DateField(null=True, blank=True, verbose_name="วันที่ชำระส่วนที่เหลือ")
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดส่วนที่เหลือ")

    doc_fe = models.BooleanField(default=False, verbose_name="ได้รับเอกสาร FE")
    doc_bl = models.BooleanField(default=False, verbose_name="ได้รับเอกสาร BL")
    doc_pl = models.BooleanField(default=False, verbose_name="ได้รับเอกสาร PL")
    doc_ci = models.BooleanField(default=False, verbose_name="ได้รับเอกสาร CI")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ใบสั่งซื้อต่างประเทศ"
        verbose_name_plural = "ใบสั่งซื้อต่างประเทศ"

    def __str__(self):
        return f"{self.supplier_name} - {self.pi_number}"