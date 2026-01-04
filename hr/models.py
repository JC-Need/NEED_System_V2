from django.db import models
from django.contrib.auth.models import User

# ==========================================
# 1. แผนก (Department)
# ==========================================
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อแผนก")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "1. แผนก"
        verbose_name_plural = "1. จัดการแผนก (Departments)"

# ==========================================
# 2. ตำแหน่ง (Position)
# ==========================================
class Position(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อตำแหน่ง")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, verbose_name="สังกัดแผนก")
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "2. ตำแหน่ง"
        verbose_name_plural = "2. จัดการตำแหน่ง (Positions)"

# ==========================================
# 3. พนักงาน (Employee)
# ==========================================
class Employee(models.Model):
    # เชื่อมกับระบบ Login ของ Django (User)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="บัญชีผู้ใช้ (Login)")
    
    # ข้อมูลส่วนตัว
    employee_id = models.CharField(max_length=20, unique=True, verbose_name="รหัสพนักงาน")
    first_name = models.CharField(max_length=100, verbose_name="ชื่อจริง")
    last_name = models.CharField(max_length=100, verbose_name="นามสกุล")
    nickname = models.CharField(max_length=50, blank=True, verbose_name="ชื่อเล่น")
    
    # การทำงาน
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, verbose_name="ตำแหน่ง")
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินเดือน")
    joined_date = models.DateField(null=True, blank=True, verbose_name="วันที่เริ่มงาน")
    
    # ติดต่อ
    phone = models.CharField(max_length=20, blank=True, verbose_name="เบอร์โทร")
    email = models.EmailField(blank=True, verbose_name="อีเมล")
    picture = models.ImageField(upload_to='employees/', blank=True, null=True, verbose_name="รูปถ่าย")
    
    is_active = models.BooleanField(default=True, verbose_name="สถานะพนักงาน (Active)")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.nickname})"

    class Meta:
        verbose_name = "3. พนักงาน"
        verbose_name_plural = "3. รายชื่อพนักงาน (Employees)"