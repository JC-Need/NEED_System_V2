from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime  # 👈 ต้องมีบรรทัดนี้ครับ สำคัญมาก!

# ==========================================
# ส่วนที่ 1: ข้อมูลประกอบ (Master Data ของ HR)
# ==========================================

class Department(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อแผนก")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "แผนก"
        verbose_name_plural = "ข้อมูลแผนก"

class Position(models.Model):
    title = models.CharField(max_length=100, verbose_name="ชื่อตำแหน่ง")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, verbose_name="สังกัดแผนก")
    
    def __str__(self):
        return f"{self.title} ({self.department})"

    class Meta:
        verbose_name = "ตำแหน่ง"
        verbose_name_plural = "ข้อมูลตำแหน่ง"

class EmployeeType(models.Model):
    name = models.CharField(max_length=50, verbose_name="ประเภทพนักงาน") 
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "ประเภทพนักงาน"
        verbose_name_plural = "ข้อมูลประเภทพนักงาน"

# ==========================================
# ส่วนที่ 2: ข้อมูลพนักงาน (Employee Core)
# ==========================================

class Employee(models.Model):
    STATUS_CHOICES = [
        ('probation', 'ทดลองงาน'),
        ('permanent', 'พนักงานประจำ'),
        ('resigned', 'ลาออก'),
    ]

    GENDER_CHOICES = [
        ('M', 'ชาย'),
        ('F', 'หญิง'),
    ]

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="User Account")
    emp_id = models.CharField(max_length=20, unique=True, verbose_name="รหัสพนักงาน")
    prefix = models.CharField(max_length=20, verbose_name="คำนำหน้า", default="คุณ")
    first_name = models.CharField(max_length=100, verbose_name="ชื่อจริง (ไทย)")
    last_name = models.CharField(max_length=100, verbose_name="นามสกุล (ไทย)")
    nickname = models.CharField(max_length=50, blank=True, verbose_name="ชื่อเล่น")
    id_card = models.CharField(max_length=13, blank=True, verbose_name="เลขบัตรประชาชน")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name="เพศ")
    birth_date = models.DateField(null=True, blank=True, verbose_name="วันเกิด")
    address = models.TextField(blank=True, verbose_name="ที่อยู่ปัจจุบัน")
    phone = models.CharField(max_length=20, verbose_name="เบอร์โทรศัพท์")
    
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, verbose_name="แผนก")
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, verbose_name="ตำแหน่ง")
    emp_type = models.ForeignKey(EmployeeType, on_delete=models.SET_NULL, null=True, verbose_name="ประเภทการจ้าง")
    start_date = models.DateField(verbose_name="วันที่เริ่มงาน", default=timezone.now)
    resign_date = models.DateField(null=True, blank=True, verbose_name="วันที่ลาออก")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='probation', verbose_name="สถานะภาพ")
    
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินเดือนปัจจุบัน")
    social_security_id = models.CharField(max_length=20, blank=True, verbose_name="เลขประกันสังคม")
    bank_account_no = models.CharField(max_length=20, blank=True, verbose_name="เลขที่บัญชี")
    
    photo = models.ImageField(upload_to='employees/', blank=True, verbose_name="รูปถ่าย")

    def __str__(self):
        return f"{self.emp_id} - {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "พนักงาน"
        verbose_name_plural = "ข้อมูลพนักงาน"
        ordering = ['emp_id']

# ==========================================
# ส่วนที่ 3: ระบบลงเวลาและการลา (Time & Attendance)
# ==========================================

class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="พนักงาน")
    date = models.DateField(verbose_name="วันที่")
    time_in = models.TimeField(null=True, blank=True, verbose_name="เวลาเข้างาน")
    time_out = models.TimeField(null=True, blank=True, verbose_name="เวลาออกงาน")
    
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="ชั่วโมงทำงานรวม")
    is_late = models.BooleanField(default=False, verbose_name="มาสาย")
    is_overtime = models.BooleanField(default=False, verbose_name="มี OT")
    
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    def save(self, *args, **kwargs):
        # ตั้งเวลาเข้างานมาตรฐาน (เช่น 08:30 น.)
        WORK_START_TIME = datetime.time(8, 30, 0)
        
        # ถ้ามีการลงเวลาเข้า
        if self.time_in:
            # เช็คว่าสายไหม? (ถ้าเวลาเข้า มากกว่า 08:30)
            if self.time_in > WORK_START_TIME:
                self.is_late = True
            else:
                self.is_late = False
                
        # คำนวณชั่วโมงทำงาน (ถ้ามีทั้งเข้าและออก)
        if self.time_in and self.time_out:
            # ต้องแปลงเป็น datetime เต็มรูปแบบเพื่อลบกัน
            dummy_date = datetime.date(2000, 1, 1)
            dt_in = datetime.datetime.combine(dummy_date, self.time_in)
            dt_out = datetime.datetime.combine(dummy_date, self.time_out)
            
            duration = dt_out - dt_in
            total_seconds = duration.total_seconds()
            self.total_hours = total_seconds / 3600 # แปลงวินาทีเป็นชั่วโมง
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.first_name} - {self.date}"

    class Meta:
        verbose_name = "บันทึกเวลาทำงาน"
        verbose_name_plural = "บันทึกเวลาทำงาน"
        unique_together = ['employee', 'date']


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('sick', 'ลาป่วย'),
        ('business', 'ลากิจ'),
        ('vacation', 'ลาพักร้อน'),
        ('other', 'อื่นๆ'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'รออนุมัติ'),
        ('approved', 'อนุมัติแล้ว'),
        ('rejected', 'ไม่อนุมัติ'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="พนักงาน")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, verbose_name="ประเภทการลา")
    start_date = models.DateField(verbose_name="วันที่เริ่มลา")
    end_date = models.DateField(verbose_name="ถึงวันที่")
    reason = models.TextField(verbose_name="เหตุผลการลา")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ผู้อนุมัติ")
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่อนุมัติ")

    def __str__(self):
        return f"{self.employee.first_name} - {self.get_leave_type_display()}"

    class Meta:
        verbose_name = "ใบลา"
        verbose_name_plural = "รายการใบลา"

# ==========================================
# ส่วนที่ 4: ระบบเงินเดือน (Payroll)
# ==========================================

class Payslip(models.Model):
    MONTH_CHOICES = [
        (1, 'มกราคม'), (2, 'กุมภาพันธ์'), (3, 'มีนาคม'), (4, 'เมษายน'),
        (5, 'พฤษภาคม'), (6, 'มิถุนายน'), (7, 'กรกฎาคม'), (8, 'สิงหาคม'),
        (9, 'กันยายน'), (10, 'ตุลาคม'), (11, 'พฤศจิกายน'), (12, 'ธันวาคม'),
    ]
    STATUS_CHOICES = [
        ('draft', 'ร่าง (ยังไม่ยืนยัน)'),
        ('published', 'อนุมัติ (พนักงานเห็นแล้ว)'),
        ('paid', 'จ่ายเงินแล้ว'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="พนักงาน")
    year = models.IntegerField(default=timezone.now().year, verbose_name="ปี ค.ศ.")
    month = models.IntegerField(choices=MONTH_CHOICES, verbose_name="เดือน")
    
    # รายรับ
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินเดือน")
    ot_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ค่าล่วงเวลา (OT)")
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="โบนัส/เบี้ยขยัน")
    other_income = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รายได้อื่นๆ")
    
    # รายจ่าย
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ภาษี ณ ที่จ่าย")
    social_security = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ประกันสังคม")
    leave_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="หักขาด/ลา/สาย")
    other_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="หักอื่นๆ")
    
    # สรุป
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินได้สุทธิ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="สถานะ")
    payment_date = models.DateField(null=True, blank=True, verbose_name="วันที่โอนเงิน")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")

    def __str__(self):
        return f"สลิปเงินเดือน: {self.employee.first_name} - {self.get_month_display()} {self.year}"
    
    def save(self, *args, **kwargs):
        # 1. ดึงเงินเดือนจากข้อมูลพนักงาน (ถ้ายังไม่ได้กรอก)
        if self.base_salary == 0:
            self.base_salary = self.employee.salary

        # 2. คำนวณประกันสังคมอัตโนมัติ (กฎหมายไทย: 5% ของเงินเดือน สูงสุดไม่เกินฐาน 15,000)
        if self.social_security == 0: # คำนวณให้เฉพาะถ้ายังไม่ได้กรอกเอง
            ss_base = self.base_salary
            if ss_base > 15000:
                ss_base = 15000
            elif ss_base < 1650: # ขั้นต่ำตามกฎหมาย
                ss_base = 1650
            
            self.social_security = ss_base * 0.05 # 5%

        # 3. คำนวณยอดสุทธิ
        total_income = self.base_salary + self.ot_pay + self.bonus + self.other_income
        total_deduction = self.tax + self.social_security + self.leave_deduction + self.other_deduction
        self.net_salary = total_income - total_deduction
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "สลิปเงินเดือน"
        verbose_name_plural = "จัดการสลิปเงินเดือน"
        unique_together = ['employee', 'year', 'month']