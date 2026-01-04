from django.db import models

# ==========================================
# 1. ข้อมูลบริษัท (Company Info)
# ==========================================
class CompanyInfo(models.Model):
    name_th = models.CharField(max_length=200, verbose_name="ชื่อบริษัท (ไทย)")
    name_en = models.CharField(max_length=200, verbose_name="ชื่อบริษัท (อังกฤษ)", blank=True)
    tax_id = models.CharField(max_length=20, verbose_name="เลขผู้เสียภาษี")
    branch = models.CharField(max_length=50, default="สำนักงานใหญ่", verbose_name="สาขา")
    
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    email = models.EmailField(blank=True, verbose_name="อีเมล")
    website = models.URLField(blank=True, verbose_name="เว็บไซต์")
    
    logo = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="โลโก้")
    signature = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="ลายเซ็น/ตราประทับ")

    class Meta:
        verbose_name = "1. ข้อมูลบริษัท"
        verbose_name_plural = "1. ตั้งค่าข้อมูลบริษัท"

    def __str__(self):
        return self.name_th

# ==========================================
# 2. ฐานข้อมูลลูกค้า (Customers)
# ==========================================
class Customer(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสลูกค้า")
    name = models.CharField(max_length=200, verbose_name="ชื่อลูกค้า/บริษัท")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="ผู้ติดต่อ")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")
    credit_term = models.IntegerField(default=0, verbose_name="เครดิต (วัน)")

    class Meta:
        verbose_name = "2. ฐานข้อมูลลูกค้า"
        verbose_name_plural = "2. จัดการลูกค้า (Debtors)"

    def __str__(self):
        return f"{self.code} - {self.name}"

# ==========================================
# 3. ฐานข้อมูลผู้ขาย (Suppliers)
# ==========================================
class Supplier(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสผู้ขาย")
    name = models.CharField(max_length=200, verbose_name="ชื่อร้านค้า/บริษัท")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="ผู้ติดต่อ")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")

    class Meta:
        verbose_name = "3. ฐานข้อมูลผู้ขาย"
        verbose_name_plural = "3. จัดการผู้ขาย (Creditors)"

    def __str__(self):
        return f"{self.code} - {self.name}"