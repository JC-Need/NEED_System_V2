from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

# --- Master Data HR ---
class Department(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อแผนก")
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "ข้อมูลแผนก"

class Position(models.Model):
    title = models.CharField(max_length=100, verbose_name="ชื่อตำแหน่ง")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, verbose_name="สังกัดแผนก")
    def __str__(self): return f"{self.title} ({self.department})"
    class Meta: verbose_name_plural = "ข้อมูลตำแหน่ง"

class EmployeeType(models.Model):
    name = models.CharField(max_length=50, verbose_name="ประเภทพนักงาน") 
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "ข้อมูลประเภทพนักงาน"

# --- Employee Core ---
class Employee(models.Model):
    STATUS_CHOICES = [('probation', 'ทดลองงาน'), ('permanent', 'พนักงานประจำ'), ('resigned', 'ลาออก')]
    GENDER_CHOICES = [('M', 'ชาย'), ('F', 'หญิง')]

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
    bank_account_no = models.CharField(max_length=20, blank=True, verbose_name="เลขที่บัญชี (เงินเดือน)")
    
    photo = models.ImageField(upload_to='employees/', blank=True, verbose_name="รูปถ่าย")

    # ✅ เพิ่มช่องเก็บลายเซ็นต์
    signature = models.ImageField(upload_to='signatures/', blank=True, null=True, verbose_name="รูปลายเซ็นต์ (สำหรับอนุมัติ)")

    # Network & Rank
    introducer = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='downlines', verbose_name='ผู้แนะนำ (Upline)')
    RANK_CHOICES = [('member', 'Member'), ('supervisor', 'Supervisor'), ('manager', 'Manager'), ('director', 'Director')]
    business_rank = models.CharField(max_length=20, choices=RANK_CHOICES, default='member', verbose_name='ระดับธุรกิจ')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='ค่าคอมมิชชั่น (%)')
    bank_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='ธนาคาร (รับคอมมิชชั่น)')
    bank_account = models.CharField(max_length=20, blank=True, null=True, verbose_name='เลขบัญชี (รับคอมมิชชั่น)')

    def __str__(self): return f"{self.emp_id} - {self.first_name} {self.last_name}"
    class Meta: verbose_name_plural = "ข้อมูลพนักงาน"

# --- ส่วนอื่นๆ (Attendance, LeaveRequest, Payslip, CommissionLog) คงเดิม ---
# (เจนี่สามารถคงโค้ดส่วน Attendance... ลงไปจนจบไฟล์เดิมไว้ได้เลยครับ)
# เพื่อความกระชับ ผมละส่วนที่ไม่เกี่ยวข้องไว้ แต่ถ้าไฟล์เดิมมีอยู่แล้ว ห้ามลบนะครับ!
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
        WORK_START_TIME = datetime.time(8, 30, 0)
        if self.time_in:
            if self.time_in > WORK_START_TIME: self.is_late = True
            else: self.is_late = False
        if self.time_in and self.time_out:
            dummy_date = datetime.date(2000, 1, 1)
            dt_in = datetime.datetime.combine(dummy_date, self.time_in)
            dt_out = datetime.datetime.combine(dummy_date, self.time_out)
            duration = dt_out - dt_in
            self.total_hours = duration.total_seconds() / 3600
        super().save(*args, **kwargs)
    class Meta: verbose_name_plural = "บันทึกเวลาทำงาน"

class LeaveRequest(models.Model):
    LEAVE_TYPES = [('sick', 'ลาป่วย'), ('business', 'ลากิจ'), ('vacation', 'ลาพักร้อน'), ('other', 'อื่นๆ')]
    STATUS_CHOICES = [('pending', 'รออนุมัติ'), ('approved', 'อนุมัติแล้ว'), ('rejected', 'ไม่อนุมัติ')]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="พนักงาน")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, verbose_name="ประเภทการลา")
    start_date = models.DateField(verbose_name="วันที่เริ่มลา")
    end_date = models.DateField(verbose_name="ถึงวันที่")
    reason = models.TextField(verbose_name="เหตุผลการลา")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ผู้อนุมัติ")
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่อนุมัติ")
    class Meta: verbose_name_plural = "รายการใบลา"

class Payslip(models.Model):
    MONTH_CHOICES = [(i, m) for i, m in enumerate(['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'], 1)]
    STATUS_CHOICES = [('draft', 'ร่าง'), ('published', 'อนุมัติ'), ('paid', 'จ่ายแล้ว')]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="พนักงาน")
    year = models.IntegerField(default=timezone.now().year, verbose_name="ปี ค.ศ.")
    month = models.IntegerField(choices=MONTH_CHOICES, verbose_name="เดือน")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="เงินเดือน")
    ot_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="OT")
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="โบนัส")
    other_income = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="รายได้อื่นๆ")
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ภาษี")
    social_security = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ประกันสังคม")
    leave_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="หักลา")
    other_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="หักอื่นๆ")
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="สุทธิ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="สถานะ")
    payment_date = models.DateField(null=True, blank=True, verbose_name="วันที่โอน")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    def save(self, *args, **kwargs):
        if self.base_salary == 0: self.base_salary = self.employee.salary
        total_income = self.base_salary + self.ot_pay + self.bonus + self.other_income
        total_deduction = self.tax + self.social_security + self.leave_deduction + self.other_deduction
        self.net_salary = total_income - total_deduction
        super().save(*args, **kwargs)
    class Meta: verbose_name_plural = "จัดการสลิปเงินเดือน"

class CommissionLog(models.Model):
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='commissions_received', verbose_name="ผู้รับเงิน")
    source_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, verbose_name="จากยอดขายของ")
    level = models.IntegerField(verbose_name="ชั้นที่")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="จำนวนเงิน")
    sale_ref_id = models.CharField(max_length=50, blank=True, verbose_name="อ้างอิง")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่ได้รับ")
    class Meta: verbose_name_plural = "ประวัติค่าคอมมิชชั่น"