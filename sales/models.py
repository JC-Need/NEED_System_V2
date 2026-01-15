from django.db import models
from django.utils import timezone
from decimal import Decimal

# Import Models ที่เกี่ยวข้อง
from master_data.models import Customer
from hr.models import Employee
from inventory.models import Product

# =========================
# 1. ระบบ POS (ขายหน้าร้าน)
# =========================
class POSOrder(models.Model):
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PAID', verbose_name="สถานะ") 
    is_commission_calculated = models.BooleanField(default=False, verbose_name="คำนวณคอมฯแล้ว")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="เวลาที่ขาย")

    def __str__(self): return self.code

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # (Logic คำนวณคอมมิชชั่น ถ้ามี)

class POSOrderItem(models.Model):
    order = models.ForeignKey(POSOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    product_name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า (ณ ตอนขาย)", null=True, blank=True)
    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อชิ้น")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคารวม")

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price
        if not self.product_name and self.product:
            self.product_name = self.product.name
        super().save(*args, **kwargs)


# =========================
# 2. ระบบ Quotation (ใบเสนอราคา)
# =========================
class Quotation(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'รอยืนยัน'),
        ('APPROVED', 'อนุมัติ/สั่งซื้อแล้ว'),
        ('REJECTED', 'ยกเลิก')
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสนอราคา")
    date = models.DateField(default=timezone.now, verbose_name="วันที่เอกสาร")
    valid_until = models.DateField(null=True, blank=True, verbose_name="ยืนราคาถึงวันที่")
    
    # ✅ Link กับลูกค้า (สำคัญมากสำหรับการดึงรหัส)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ลูกค้า (Link)")
    
    # ข้อมูลลูกค้า (Text Snapshot - เผื่อแก้ไขเฉพาะงาน)
    customer_name = models.CharField(max_length=200, verbose_name="ชื่อลูกค้า (ระบุเอง)", blank=True)
    customer_address = models.TextField(verbose_name="ที่อยู่", blank=True)
    customer_tax_id = models.CharField(max_length=20, verbose_name="เลขผู้เสียภาษี", blank=True)
    customer_phone = models.CharField(max_length=50, verbose_name="เบอร์โทร", blank=True)
    
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ออกใบเสนอราคา")
    
    # ตัวเลขการเงิน
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รวมราคาสินค้า")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ส่วนลด")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ค่าขนส่ง")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ภาษีมูลค่าเพิ่ม")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดสุทธิ")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="สถานะ")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.code

    # ✅ เพิ่ม Property นี้: เพื่อให้ Template เรียกใช้ {{ qt.customer_code }} ได้เลย
    @property
    def customer_code(self):
        if self.customer:
            return self.customer.code
        return None

class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    item_name = models.CharField(max_length=200, verbose_name="ชื่อรายการสินค้า")
    description = models.CharField(max_length=255, blank=True, null=True)
    
    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อหน่วย")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="รวมเงิน")

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)