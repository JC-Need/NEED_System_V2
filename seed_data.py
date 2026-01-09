import os
import django
import random
from datetime import date, timedelta

# ตั้งค่า Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from hr.models import Department, Position, EmployeeType, Employee

# ==========================================
# 1. ข้อมูลตั้งต้น (Master Data)
# ==========================================
def create_master_data():
    print("🚀 กำลังสร้างข้อมูลแผนกและตำแหน่ง...")
    
    structure = {
        "Executive": ["CEO", "Secretary"],
        "Human Resources": ["HR Manager", "Recruiter", "Admin Staff"],
        "Accounting & Finance": ["Finance Manager", "Accountant", "Cashier"],
        "Sales & Marketing": ["Sales Director", "Sales Manager", "Team Leader", "Sales Representative"],
        "Manufacturing": ["Factory Manager", "Production Supervisor", "Machine Operator", "Quality Control"],
        "Purchasing & Inventory": ["Purchasing Manager", "Stock Controller", "Warehouse Staff"],
        "IT Support": ["IT Manager", "Developer", "System Admin"]
    }

    dept_objs = {}
    pos_objs = {}

    for dept_name, positions in structure.items():
        # สร้างแผนก
        d, _ = Department.objects.get_or_create(name=dept_name)
        dept_objs[dept_name] = d
        
        # สร้างตำแหน่ง
        for pos_title in positions:
            p, _ = Position.objects.get_or_create(title=pos_title, department=d)
            pos_objs[pos_title] = p

    # สร้างประเภทพนักงาน
    etype_perm, _ = EmployeeType.objects.get_or_create(name="พนักงานประจำ")
    etype_prob, _ = EmployeeType.objects.get_or_create(name="ทดลองงาน")
    
    return dept_objs, pos_objs, [etype_perm, etype_prob]

# ==========================================
# 2. รายชื่อพนักงานจำลอง (Mock Names)
# ==========================================
THAI_NAMES = [
    ("สมชาย", "ใจดี", "M"), ("สมหญิง", "รักงาน", "F"), ("วิชัย", "เก่งกาจ", "M"), 
    ("มานี", "มีตา", "F"), ("ชูใจ", "สีฟ้า", "F"), ("ปิติ", "พอใจ", "M"),
    ("มานะ", "อดทน", "M"), ("วีระ", "กล้าหาญ", "M"), ("ดวงใจ", "สดใส", "F"),
    ("อำนาจ", "ครองเมือง", "M"), ("สุดา", "สวยงาม", "F"), ("ธีระ", "ปัญญางาม", "M"),
    ("กานดา", "น่ารัก", "F"), ("นพดล", "ดวงดี", "M"), ("รัตนา", "วงค์สวัสดิ์", "F"),
    ("ประเสริฐ", "เลิศล้ำ", "M"), ("วันเพ็ญ", "จันทร์เจ้า", "F"), ("สุชาติ", "แคล้วคลาด", "M"),
    ("พรทิพย์", "โรจนัย", "F"), ("เอกชัย", "ศรีวิชัย", "M"), ("จินตนา", "สุขใจ", "F"),
    ("ธนพล", "รวยทรัพย์", "M"), ("กมลชนก", "โกมล", "F"), ("วรเวช", "ดานุวงศ์", "M"),
    ("พิมพ์ชนก", "ลือวิเศษไพบูลย์", "F"), ("ณเดชน์", "คูกิมิยะ", "M"), ("อุรัสยา", "เสปอร์บันด์", "F"),
    ("ปริญ", "สุภารัตน์", "M"), ("ราณี", "แคมเปน", "F"), ("จิรายุ", "ตั้งศรีสุข", "M")
]

# ==========================================
# 3. ฟังก์ชันสร้างพนักงาน
# ==========================================
def create_employees(depts, positions, etypes):
    print("👥 กำลังจ้างพนักงานและจัดสายงาน (Network)...")
    
    # --- LEVEL 0: CEO (Root Node) ---
    # ใช้ User admin ที่มีอยู่แล้ว หรือสร้างใหม่ถ้าจำเป็น
    ceo_user, _ = User.objects.get_or_create(username='ceo', defaults={'email': 'ceo@need.com'})
    if _: ceo_user.set_password('1234')
    ceo_user.save()

    ceo, created = Employee.objects.get_or_create(
        emp_id="EMP-001",
        defaults={
            'prefix': 'คุณ', 'first_name': 'เจษฎา', 'last_name': 'ผู้บริหาร', 'nickname': 'บอส',
            'gender': 'M', 'user': ceo_user,
            'department': depts['Executive'], 'position': positions['CEO'],
            'emp_type': etypes[0], 'salary': 150000,
            'start_date': date(2020, 1, 1), 'status': 'permanent',
            'business_rank': 'director', 'commission_rate': 10.00
        }
    )
    print(f"   ✅ Created CEO: {ceo.first_name}")

    all_employees = [ceo]
    
    # --- LEVEL 1: Managers (ลูกติดตัว CEO) ---
    managers = []
    manager_configs = [
        ('HR', 'Human Resources', 'HR Manager', 'F'),
        ('ACC', 'Accounting & Finance', 'Finance Manager', 'F'),
        ('SALE', 'Sales & Marketing', 'Sales Director', 'M'),
        ('MFG', 'Manufacturing', 'Factory Manager', 'M'),
        ('PUR', 'Purchasing & Inventory', 'Purchasing Manager', 'F'),
        ('IT', 'IT Support', 'IT Manager', 'M')
    ]

    for i, (code, dept, pos, gender) in enumerate(manager_configs):
        fname, lname, g = THAI_NAMES[i]
        emp = create_one_employee(
            i+2, fname, lname, gender, depts[dept], positions[pos], etypes[0], 
            salary=80000, rank='manager', upline=ceo
        )
        managers.append(emp)
        all_employees.append(emp)

    # --- LEVEL 2 & 3: Staff & Downlines (ลูกทีม) ---
    # วนลูปรายชื่อที่เหลือ เพื่อสร้างลูกทีม
    remaining_names = THAI_NAMES[6:]
    emp_counter = 8
    
    for i, (fname, lname, gender) in enumerate(remaining_names):
        # สุ่มแผนก (เน้นฝ่ายขายเยอะหน่อย เพื่อดู Network)
        rand_val = random.random()
        if rand_val < 0.5: # 50% เป็นฝ่ายขาย
            dept = depts['Sales & Marketing']
            pos = positions['Sales Representative']
            upline = managers[2] # Sales Director
            rank = 'member'
            salary = 20000
        elif rand_val < 0.8: # 30% เป็นฝ่ายผลิต
            dept = depts['Manufacturing']
            pos = positions['Machine Operator']
            upline = managers[3] # Factory Manager
            rank = 'member'
            salary = 18000
        else: # 20% อื่นๆ
            dept = depts['Human Resources']
            pos = positions['Admin Staff']
            upline = managers[0] # HR Manager
            rank = 'member'
            salary = 15000

        # สุ่มให้มีสายงานลึกลงไปอีก (ลูกทีมของลูกทีม)
        # ถ้าคนก่อนหน้าอยู่ฝ่ายขาย ให้คนนี้ไปต่อท้ายคนเมื่อกี้
        if i > 0 and all_employees[-1].department.name == 'Sales & Marketing' and random.random() > 0.5:
            upline = all_employees[-1] 

        emp = create_one_employee(
            emp_counter, fname, lname, gender, dept, pos, etypes[0], 
            salary=salary, rank=rank, upline=upline
        )
        all_employees.append(emp)
        emp_counter += 1

    print(f"🎉 เสร็จสิ้น! สร้างพนักงานทั้งหมด {len(all_employees)} คน")

def create_one_employee(idx, fname, lname, gender, dept, pos, etype, salary, rank, upline):
    emp_id = f"EMP-{idx:03d}"
    
    # สร้าง User Login
    username = f"user{idx}"
    user, _ = User.objects.get_or_create(username=username, defaults={'email': f'{username}@need.com'})
    if _: user.set_password('1234')
    user.save()

    emp, created = Employee.objects.get_or_create(
        emp_id=emp_id,
        defaults={
            'prefix': 'คุณ', 'first_name': fname, 'last_name': lname, 'nickname': fname[:2],
            'gender': gender, 'user': user,
            'department': dept, 'position': pos, 'emp_type': etype,
            'salary': salary, 'start_date': date(2024, random.randint(1,12), random.randint(1,28)),
            'status': 'permanent',
            'business_rank': rank, 
            'commission_rate': 0.00,
            'introducer': upline # ✅ ผูก Network ตรงนี้
        }
    )
    return emp

# ==========================================
# Run Script
# ==========================================
if __name__ == '__main__':
    depts, positions, etypes = create_master_data()
    create_employees(depts, positions, etypes)