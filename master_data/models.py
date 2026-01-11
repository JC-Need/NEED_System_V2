from django.db import models

# ==========================================
# 1. ข้อมูลบริษัท (Company Info) - *หัวใจหลัก*
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

    # รูปภาพสำหรับ Branding
    logo = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="โลโก้เอกสาร (Square)")
    login_image = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="รูปหน้า Login (ใหญ่)")
    navbar_image = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="โลโก้บนแถบเมนู (แนวนอน)")
    signature = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="ลายเซ็น/ตราประทับ")

    class Meta:
        verbose_name = "ข้อมูลบริษัท"
        verbose_name_plural = "1. ตั้งค่าข้อมูลบริษัท"

    def __str__(self):
        return self.name_th

# ==========================================
# 2. คู่ค้าทางธุรกิจ (Business Partners) - *ใช้ร่วมกันหลายฝ่าย*
# ==========================================
class Customer(models.Model):
    """
    ลูกค้า: ใช้โดยฝ่ายขาย (Sales), บัญชี (Accounting), คลัง (Inventory-ตัดของ)
    """
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสลูกค้า")
    name = models.CharField(max_length=200, verbose_name="ชื่อลูกค้า")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    email = models.EmailField(blank=True, verbose_name="อีเมล")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")
    credit_term = models.IntegerField(default=30, verbose_name="เครดิต (วัน)")
    points = models.IntegerField(default=0, verbose_name="คะแนนสะสม")

    class Meta:
        verbose_name = "ลูกค้า"
        verbose_name_plural = "2. ฐานข้อมูลลูกค้า (Debtors)"
    
    def __str__(self): 
        return f"{self.code} - {self.name}"

class Supplier(models.Model):
    """
    ผู้ขาย/ซัพพลายเออร์: ใช้โดยฝ่ายจัดซื้อ (Purchasing), คลัง (Inventory-รับของ), บัญชี (Accounting)
    """
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสผู้ขาย")
    name = models.CharField(max_length=200, verbose_name="ชื่อผู้ขาย")
    contact_name = models.CharField(max_length=100, blank=True, verbose_name="ชื่อผู้ติดต่อ")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")
    
    class Meta:
        verbose_name = "ผู้ขาย"
        verbose_name_plural = "3. ฐานข้อมูลผู้ขาย (Creditors)"
    
    def __str__(self): 
        return f"{self.code} - {self.name}"