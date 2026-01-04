from django.db import models
from django.utils import timezone

# Import เพื่อนบ้าน (ดึงข้อมูลจากแผนกอื่น)
from master_data.models import Customer
from hr.models import Employee
from inventory.models import Product

# ==========================================
# 🛒 ส่วนที่ 1: ระบบขายหน้าร้าน (POS)
# ==========================================
class POSOrder(models.Model):
    # หัวบิล
    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสร็จ")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="พนักงานขาย")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="สมาชิก (ถ้ามี)")
    
    # เงินๆ ทองๆ
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดรวม")
    received_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รับเงินมา")
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินทอน")
    
    payment_method = models.CharField(max_length=50, choices=[('CASH','เงินสด'), ('QR','โอน/สแกน')], default='CASH', verbose_name="วิธีชำระ")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="เวลาที่ขาย")

    class Meta:
        verbose_name = "1. บิลขายหน้าร้าน (POS)"
        verbose_name_plural = "1. ประวัติการขาย POS"

    def __str__(self):
        return f"{self.code} - {self.total_amount:,.2f} บาท"

class POSOrderItem(models.Model):
    # รายการสินค้าในบิล
    order = models.ForeignKey(POSOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    product_name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า (ณ ตอนขาย)") # เก็บชื่อไว้กันสินค้าเปลี่ยนชื่อ
    
    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อชิ้น")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคารวม")

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price
        super().save(*args, **kwargs)

# ==========================================
# 📄 ส่วนที่ 2: ระบบใบเสนอราคา (Quotation)
# ==========================================
class Quotation(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'รอยืนยัน'),
        ('SENT', 'ส่งให้ลูกค้าแล้ว'),
        ('APPROVED', 'อนุมัติ/สั่งซื้อแล้ว'),
        ('REJECTED', 'ยกเลิก/ไม่ผ่าน')
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสนอราคา")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, verbose_name="ลูกค้า")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ออกใบเสนอราคา")
    
    date = models.DateField(default=timezone.now, verbose_name="วันที่เอกสาร")
    valid_until = models.DateField(null=True, blank=True, verbose_name="ยืนราคาถึงวันที่")
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รวมเป็นเงิน")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ส่วนลด")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ภาษีมูลค่าเพิ่ม (7%)")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดสุทธิ")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="สถานะ")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    class Meta:
        verbose_name = "2. ใบเสนอราคา (Quotation)"
        verbose_name_plural = "2. จัดการใบเสนอราคา"

    def __str__(self):
        return f"{self.code} - {self.customer}"

class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    description = models.CharField(max_length=255, blank=True, verbose_name="รายละเอียดเพิ่มเติม")
    
    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อหน่วย")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="จำนวนเงิน")

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)