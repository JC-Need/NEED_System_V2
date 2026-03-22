from django.db import models
from django.utils import timezone
from decimal import Decimal
from master_data.models import Customer
from hr.models import Employee
from inventory.models import Product
from PIL import Image

class POSOrder(models.Model):
    STATUS_CHOICES = [('PENDING', 'รอชำระเงิน'), ('PAID', 'ชำระเงินแล้ว'), ('CANCELLED', 'ยกเลิก')]
    PAYMENT_CHOICES = [('CASH', 'เงินสด'), ('TRANSFER', 'โอนเงิน'), ('CHECK', 'เช็คธนาคาร')]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสร็จ")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="พนักงานขาย")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ลูกค้า (สมาชิก)")
    customer_name = models.CharField(max_length=200, blank=True, verbose_name="ชื่อลูกค้า (ระบุเอง)")
    customer_address = models.TextField(blank=True, verbose_name="ที่อยู่")
    customer_tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    customer_phone = models.CharField(max_length=20, blank=True, verbose_name="เบอร์โทรศัพท์")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดรวม")
    received_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รับเงินมา")
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินทอน")
    payment_method = models.CharField(max_length=50, choices=PAYMENT_CHOICES, default='CASH', verbose_name="วิธีชำระ")
    transfer_slip = models.ImageField(upload_to='pos_slips/%Y/%m/', null=True, blank=True, verbose_name="สลิปโอนเงิน")
    check_number = models.CharField(max_length=50, blank=True, verbose_name="เลขที่เช็ค")
    check_bank = models.CharField(max_length=100, blank=True, verbose_name="ธนาคารเช็ค")
    check_slip = models.ImageField(upload_to='pos_checks/%Y/%m/', null=True, blank=True, verbose_name="รูปถ่ายเช็ค")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PAID', verbose_name="สถานะ") 
    is_commission_calculated = models.BooleanField(default=False, verbose_name="คำนวณคอมฯแล้ว")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="เวลาที่ขาย")
    
    def __str__(self): return self.code

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.transfer_slip:
            try:
                img = Image.open(self.transfer_slip.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    img.save(self.transfer_slip.path, quality=85, optimize=True)
            except Exception: pass
        if self.check_slip:
            try:
                img = Image.open(self.check_slip.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    img.save(self.check_slip.path, quality=85, optimize=True)
            except Exception: pass

class POSOrderItem(models.Model):
    order = models.ForeignKey(POSOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="สินค้า")
    product_name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า (ณ ตอนขาย)", null=True, blank=True)
    quantity = models.IntegerField(default=1, verbose_name="จำนวน")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาต่อชิ้น")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคารวม")
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price
        if not self.product_name and self.product: self.product_name = self.product.name
        super().save(*args, **kwargs)

class Quotation(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'รออนุมัติ'),     
        ('APPROVED', 'อนุมัติแล้ว'), 
        ('CONVERTED', 'เปิดบิลขายแล้ว'), 
        ('REJECTED', 'ไม่อนุมัติ'),
        ('CANCELLED', 'ยกเลิกแล้ว')  
    ]
    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบเสนอราคา")
    date = models.DateField(default=timezone.now, verbose_name="วันที่เอกสาร")
    valid_until = models.DateField(null=True, blank=True, verbose_name="ยืนราคาถึงวันที่")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ลูกค้า (Link)")
    customer_name = models.CharField(max_length=200, verbose_name="ชื่อลูกค้า (ระบุเอง)", blank=True)
    customer_address = models.TextField(verbose_name="ที่อยู่", blank=True)
    customer_tax_id = models.CharField(max_length=20, verbose_name="เลขผู้เสียภาษี", blank=True)
    customer_phone = models.CharField(max_length=50, verbose_name="เบอร์โทร", blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ออกใบเสนอราคา")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รวมราคาสินค้า")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ส่วนลด")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ค่าขนส่ง")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ภาษีมูลค่าเพิ่ม")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดสุทธิ")
    
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดมัดจำที่รับแล้ว")
    deposit_date = models.DateField(null=True, blank=True, verbose_name="วันที่รับมัดจำ")
    deposit_method = models.CharField(max_length=50, blank=True, null=True, verbose_name="ช่องทางรับมัดจำ")
    deposit_slip = models.ImageField(upload_to='deposit_slips/%Y/%m/', null=True, blank=True, verbose_name="สลิปมัดจำ")
    is_deposit_paid = models.BooleanField(default=False, verbose_name="รับมัดจำแล้ว")
    is_deposit_verified = models.BooleanField(default=False, verbose_name="บัญชีตรวจสอบมัดจำแล้ว")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="สถานะ")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_quotations', verbose_name="ผู้อนุมัติ")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="วันที่อนุมัติ")

    def __str__(self): return self.code
    @property
    def customer_code(self): return self.customer.code if self.customer else None

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.deposit_slip:
            try:
                img = Image.open(self.deposit_slip.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    img.save(self.deposit_slip.path, quality=85, optimize=True)
            except Exception: pass

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

class Invoice(models.Model):
    PAYMENT_CHOICES = [('CASH', 'เงินสด'), ('TRANSFER', 'โอนเงิน'), ('CHECK', 'เช็คธนาคาร')]

    code = models.CharField(max_length=20, unique=True, verbose_name="เลขที่ใบกำกับภาษี/ใบเสร็จ")
    quotation_ref = models.OneToOneField(Quotation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="อ้างอิงใบเสนอราคา")
    date = models.DateField(default=timezone.now, verbose_name="วันที่เอกสาร")
    due_date = models.DateField(null=True, blank=True, verbose_name="ครบกำหนดชำระ")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, verbose_name="ลูกค้า")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="พนักงานขาย")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดสุทธิ")
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="หักมัดจำ")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ยอดคงค้างชำระ")
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_CHOICES, blank=True, null=True, verbose_name="วิธีชำระเงิน")
    payment_date = models.DateField(null=True, blank=True, verbose_name="วันที่ชำระเงิน")
    transfer_slip = models.ImageField(upload_to='invoice_slips/%Y/%m/', null=True, blank=True, verbose_name="สลิปโอนเงิน")
    check_number = models.CharField(max_length=50, blank=True, verbose_name="เลขที่เช็ค")
    check_bank = models.CharField(max_length=100, blank=True, verbose_name="ธนาคารเช็ค")
    check_slip = models.ImageField(upload_to='invoice_checks/%Y/%m/', null=True, blank=True, verbose_name="รูปถ่ายเช็ค")

    status = models.CharField(max_length=20, choices=[('UNPAID', 'ยังไม่ชำระ'), ('PAID', 'ชำระแล้ว'), ('PENDING', 'รอตรวจสอบ')], default='UNPAID', verbose_name="สถานะ")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): return self.code

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.transfer_slip:
            try:
                img = Image.open(self.transfer_slip.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    img.save(self.transfer_slip.path, quality=85, optimize=True)
            except Exception: pass
        if self.check_slip:
            try:
                img = Image.open(self.check_slip.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    img.save(self.check_slip.path, quality=85, optimize=True)
            except Exception: pass

# ==========================================
# 🌟 [เพิ่มใหม่] ส่วนของแคตตาล็อก Upsale 🌟
# ==========================================
class UpsaleCatalog(models.Model):
    name = models.CharField(max_length=200, verbose_name="ชื่อรายการปรับเปลี่ยน/เพิ่มเติม")
    default_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคามาตรฐาน")
    unit = models.CharField(max_length=50, blank=True, null=True, default="รายการ", verbose_name="หน่วยนับ")
    is_active = models.BooleanField(default=True, verbose_name="เปิดใช้งาน")

    def __str__(self):
        return self.name

class QuotationUpsale(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='upsales', on_delete=models.CASCADE)
    description = models.CharField(max_length=255, verbose_name="รายการเพิ่มเติม")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} ({self.quotation.code})"