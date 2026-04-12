from django.db import models
from django.utils import timezone
from inventory.models import Product
from hr.models import Employee
import datetime

# ==========================================
# 🌟 ตารางสำหรับเก็บข้อมูลลูกค้าและทีมงาน 🌟
# ==========================================
class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อสาขา")
    def __str__(self): return self.name

class Salesperson(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='salespersons', verbose_name="สาขา")
    name = models.CharField(max_length=100, verbose_name="ชื่อพนักงานขาย")
    def __str__(self): return f"{self.name} ({self.branch.name})"

# ==========================================
# 🌟 ตารางใหม่: สำหรับระบบกระดานติดตามงาน 🌟
# ==========================================
class ProductionStatus(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="สถานะการผลิตหน้างาน (แผนก)")
    sequence = models.IntegerField(default=99, verbose_name="ลำดับการแสดงผล")
    class Meta: ordering = ['sequence', 'id'] 
    def __str__(self): return self.name

class ProductionTeam(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อทีมช่าง")
    def __str__(self): return self.name

class DeliveryStatus(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="สถานะการจัดส่ง")
    def __str__(self): return self.name

class Transporter(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ทีมขนส่ง / บริษัทขนส่ง")
    def __str__(self): return self.name

# ==========================================
# 1. สูตรการผลิต (Bill of Materials - BOM)
# ==========================================
class BOM(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, verbose_name="สินค้าสำเร็จรูป (FG)")
    name = models.CharField(max_length=200, verbose_name="ชื่อสูตร (เช่น สูตรมาตรฐาน)")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    def __str__(self): return f"สูตรผลิต: {self.product.name}"
    class Meta:
        verbose_name = "1. สูตรการผลิต (BOM)"
        verbose_name_plural = "1. จัดการสูตรผลิต"

class BOMItem(models.Model):
    bom = models.ForeignKey(BOM, related_name='items', on_delete=models.CASCADE)
    raw_material = models.ForeignKey(Product, related_name='used_in_boms', on_delete=models.CASCADE, verbose_name="วัตถุดิบ (Raw Mat)")
    quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="จำนวนที่ใช้ (ต่อ 1 หน่วยผลิต)")
    def __str__(self): return f"{self.raw_material.name} ({self.quantity})"

# ==========================================
# 2. ใบสั่งผลิต (Production Order - JOB)
# ==========================================
class ProductionOrder(models.Model):
    STATUS_CHOICES = [
        ('PLANNED', 'รอตรวจสอบแบบแปลน'),
        ('WAITING_MATERIALS', 'รอสั่งซื้อวัตถุดิบ'),
        ('WAITING_INVENTORY', 'รอวัตถุดิบพร้อมผลิต'),
        ('IN_PROGRESS', 'งานอยู่ระหว่างผลิต'),
        ('COMPLETED', 'ผลิตเสร็จแล้ว (เข้าสต็อก)'),
        ('CANCELLED', 'ยกเลิก')
    ]

    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="เลขที่ใบสั่งผลิต (JOB)")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่จะผลิต")
    quantity = models.IntegerField(default=1, verbose_name="จำนวนที่ผลิต (ล็อกที่ 1 เสมอ)")
    quotation_ref = models.ForeignKey('sales.Quotation', on_delete=models.SET_NULL, null=True, blank=True, related_name='production_orders', verbose_name="อ้างอิงใบเสนอราคา/มัดจำ")
    blueprint_file = models.FileField(upload_to='blueprints/%Y/%m/', null=True, blank=True, verbose_name="ไฟล์แบบแปลน (PDF/รูปภาพ)")
    
    start_date = models.DateField(default=timezone.now, verbose_name="วันที่เริ่มผลิต")
    finish_date = models.DateField(null=True, blank=True, verbose_name="วันที่เสร็จ (เข้าคลัง)")
    delivery_date = models.DateField(null=True, blank=True, verbose_name="กำหนดจัดส่งสินค้า")
    
    # 🌟 [NEW] ข้อมูลสำหรับคุมคิว 25 งาน/สัปดาห์ และ SLA 22 วัน 🌟
    cohort_week = models.CharField(max_length=15, blank=True, null=True, verbose_name="สัปดาห์คิวผลิต (Cohort)")
    deadline_date = models.DateField(null=True, blank=True, verbose_name="เส้นตายจัดส่ง (SLA)")

    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="สาขาที่ขาย")
    salesperson = models.ForeignKey(Salesperson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="พนักงานขาย")
    customer_name = models.CharField(max_length=200, blank=True, verbose_name="ชื่อลูกค้า / สถานที่ส่ง")
    completed_departments = models.ManyToManyField(ProductionStatus, blank=True, verbose_name="แผนกที่ดำเนินการเสร็จแล้ว")
    production_team = models.ForeignKey(ProductionTeam, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ทีมช่างผลิต")
    delivery_status = models.ForeignKey(DeliveryStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="สถานะจัดส่ง")
    transporter = models.ForeignKey(Transporter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ทีมขนส่ง")
    
    responsible_person = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="ผู้ควบคุมการผลิต")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED', verbose_name="สถานะระบบ")
    is_materials_ordered = models.BooleanField(default=False, verbose_name="สั่งซื้อวัตถุดิบแล้ว")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    is_closed = models.BooleanField(default=False, verbose_name="ปิดจ๊อบแล้ว (งานเสร็จสมบูรณ์)")

    class Meta:
        verbose_name = "2. ใบสั่งผลิต"
        verbose_name_plural = "2. จัดการการผลิต"

    def __str__(self): return f"{self.code} - {self.product.name}"

    def save(self, *args, **kwargs):
        self.quantity = 1 
        if not self.code:
            today = datetime.date.today()
            thai_year = (today.year + 543) % 100
            prefix = f"JOB{thai_year:02d}{today.strftime('%m')}"
            last_order = ProductionOrder.objects.filter(code__startswith=prefix).order_by('code').last()
            if last_order:
                try: seq = int(last_order.code.replace(prefix, '')) + 1
                except: seq = 1
            else: seq = 1
            self.code = f"{prefix}{seq:03d}"
        super().save(*args, **kwargs)

    @property
    def progress_percentage(self):
        total_depts = ProductionStatus.objects.count()
        if total_depts == 0: return 0
        return int((self.completed_departments.count() / total_depts) * 100)

    # 🌟 [NEW] สูตรคำนวณวันคงเหลือ เพื่อแสดงแถบสีในการ์ด Planner 🌟
    @property
    def days_remaining(self):
        if not self.deadline_date or self.is_closed: return 0
        return (self.deadline_date - datetime.date.today()).days

    @property
    def sla_status_color(self):
        if self.is_closed: return "success"
        rem = self.days_remaining
        if rem < 0: return "danger" # เลยกำหนด (แดง)
        if rem <= 5: return "warning" # ใกล้ถึงกำหนด (เหลือง/ส้ม)
        return "primary" # ปลอดภัย (น้ำเงิน)

# ==========================================
# 3. รายการวัตถุดิบที่ใช้จริงต่อ 1 งาน (Job Material List)
# ==========================================
class ProductionOrderMaterial(models.Model):
    production_order = models.ForeignKey(ProductionOrder, related_name='materials', on_delete=models.CASCADE)
    raw_material = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="วัตถุดิบ")
    quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="จำนวนที่ต้องใช้")
    is_additional = models.BooleanField(default=False, verbose_name="เป็นรายการสั่งเพิ่มพิเศษ (ไม่อยู่ใน BOM)")

    def __str__(self): return f"{self.production_order.code} - {self.raw_material.name}"
    class Meta:
        verbose_name = "3. วัตถุดิบในใบสั่งผลิต"
        verbose_name_plural = "3. จัดการวัตถุดิบในงานผลิต"