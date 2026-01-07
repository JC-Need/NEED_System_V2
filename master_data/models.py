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

    # ส่วนรูปภาพที่ปรับแต่งได้เองตามโจทย์
    logo = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="โลโก้เอกสาร (Square)")
    login_image = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="รูปหน้า Login (ใหญ่)")
    navbar_image = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="โลโก้บนแถบเมนู (แนวนอน)")
    signature = models.ImageField(upload_to='company/', blank=True, null=True, verbose_name="ลายเซ็น/ตราประทับ")

    class Meta:
        verbose_name = "1. ข้อมูลบริษัท"
        verbose_name_plural = "1. ตั้งค่าข้อมูลบริษัท"

    def __str__(self):
        return self.name_th

# ==========================================
# 2. โครงสร้างองค์กร (Organization) - *เพิ่มใหม่สำหรับ HR*
# ==========================================
class Department(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อแผนก")
    
    class Meta:
        verbose_name = "แผนก"
        verbose_name_plural = "2.1 แผนก (Departments)"
    def __str__(self): return self.name

class Position(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อตำแหน่ง")
    level = models.IntegerField(default=1, verbose_name="ระดับ (1=พนักงาน, 9=ผู้บริหาร)")
    
    class Meta:
        verbose_name = "ตำแหน่ง"
        verbose_name_plural = "2.2 ตำแหน่ง (Positions)"
    def __str__(self): return self.name

# ==========================================
# 3. คู่ค้า (Business Partners)
# ==========================================
class Customer(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสลูกค้า")
    name = models.CharField(max_length=200, verbose_name="ชื่อลูกค้า")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    email = models.EmailField(blank=True, verbose_name="อีเมล")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")
    credit_term = models.IntegerField(default=30, verbose_name="เครดิต (วัน)")

    class Meta:
        verbose_name = "ลูกค้า"
        verbose_name_plural = "3. ฐานข้อมูลลูกค้า (Debtors)"
    def __str__(self): return f"{self.code} - {self.name}"

class Supplier(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสผู้ขาย")
    name = models.CharField(max_length=200, verbose_name="ชื่อผู้ขาย")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขผู้เสียภาษี")
    phone = models.CharField(max_length=50, blank=True, verbose_name="เบอร์โทร")
    address = models.TextField(blank=True, verbose_name="ที่อยู่")
    
    class Meta:
        verbose_name = "ผู้ขาย"
        verbose_name_plural = "4. ฐานข้อมูลผู้ขาย (Creditors)"
    def __str__(self): return f"{self.code} - {self.name}"

# ==========================================
# 4. สินค้าและบริการ (Products) - *เพิ่มใหม่สำหรับ Sales/Inventory*
# ==========================================
class Unit(models.Model):
    name = models.CharField(max_length=50, verbose_name="หน่วยนับ (เช่น ชิ้น, กล่อง)")
    class Meta: verbose_name_plural = "5.1 หน่วยนับ"; 
    def __str__(self): return self.name

class ProductCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="หมวดหมู่สินค้า")
    class Meta: verbose_name_plural = "5.2 หมวดหมู่สินค้า"; 
    def __str__(self): return self.name

class Product(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="รหัสสินค้า (SKU)")
    name = models.CharField(max_length=200, verbose_name="ชื่อสินค้า")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, verbose_name="หมวดหมู่")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, verbose_name="หน่วยนับ")
    price_buy = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาซื้อมาตรฐาน")
    price_sell = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาขายมาตรฐาน")
    is_active = models.BooleanField(default=True, verbose_name="ใช้งานอยู่")

    class Meta:
        verbose_name = "สินค้า"
        verbose_name_plural = "5. ฐานข้อมูลสินค้า (Products)"
    def __str__(self): return f"{self.code} - {self.name}"