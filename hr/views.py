from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum
from datetime import datetime, date, timedelta 
from django.contrib.auth.models import User # Import User

from .models import Employee, Attendance, LeaveRequest, Payslip, CommissionLog 
from .forms import LeaveRequestForm, EmployeeForm

# ==========================================
# 1. หน้า Dashboard พนักงาน (Employee Zone)
# ==========================================
@login_required(login_url='/login/')
def employee_dashboard(request):
    try:
        employee = request.user.employee
    except AttributeError:
        return render(request, 'hr/error_no_profile.html')

    # --- 🔍 ส่วนกรองวันที่ (Date Filter Logic) ---
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # ถ้าไม่ได้เลือกวันที่มา ให้ใช้ค่าเริ่มต้น (วันที่ 1 ของเดือนปัจจุบัน - วันนี้)
    if not start_date_str or not end_date_str:
        today = date.today()
        start_date_str = today.replace(day=1).strftime('%Y-%m-%d') # วันที่ 1
        end_date_str = today.strftime('%Y-%m-%d') # วันนี้

    # --- 📥 ดึงข้อมูล ---
    latest_payslip = Payslip.objects.filter(employee=employee, status='published').order_by('-year', '-month').first()
    today_attendance = Attendance.objects.filter(employee=employee, date=date.today()).first()
    leaves = LeaveRequest.objects.filter(employee=employee).order_by('-start_date')[:5]

    # ประวัติเวลาเข้า-ออก (Attendance Log)
    attendance_history = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date_str, end_date_str]
    ).order_by('-date')

    context = {
        'employee': employee,
        'payslip': latest_payslip,
        'leaves': leaves,
        'today_attendance': today_attendance,
        'attendance_history': attendance_history,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    return render(request, 'hr/dashboard.html', context)


# ==========================================
# 2. ระบบลงเวลา (Check-in / Check-out)
# ==========================================
@login_required
def check_in(request):
    if request.method == 'POST':
        try:
            employee = request.user.employee
            today = date.today()
            attendance, created = Attendance.objects.get_or_create(employee=employee, date=today)

            if not attendance.time_in:
                attendance.time_in = timezone.localtime(timezone.now()).time()
                attendance.save()
                messages.success(request, f'ลงเวลาเข้างานเรียบร้อย ({attendance.time_in.strftime("%H:%M")})')

        except Exception as e:
            print(f"Error checking in: {e}")

    return redirect('employee_dashboard')

@login_required
def check_out(request):
    if request.method == 'POST':
        try:
            employee = request.user.employee
            today = date.today()
            attendance = Attendance.objects.filter(employee=employee, date=today).first()

            if attendance:
                attendance.time_out = timezone.localtime(timezone.now()).time()
                attendance.save()
                messages.success(request, f'ลงเวลาออกงานเรียบร้อย ({attendance.time_out.strftime("%H:%M")})')

        except Exception as e:
            print(f"Error checking out: {e}")

    return redirect('employee_dashboard')


# ==========================================
# 3. ระบบการลา (Leave Request)
# ==========================================
@login_required
def leave_create(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = request.user.employee
            leave_request.save()

            messages.success(request, 'ส่งใบลาเรียบร้อยแล้ว รอหัวหน้าอนุมัติครับ')
            return redirect('employee_dashboard')
    else:
        form = LeaveRequestForm()

    return render(request, 'hr/leave_form.html', {'form': form})


# ==========================================
# 4. ส่วนของผู้จัดการ (Manager Zone)
# ==========================================
@staff_member_required(login_url='/login/')
def manager_dashboard(request):
    pending_leaves = LeaveRequest.objects.filter(status='pending').order_by('start_date')
    history_leaves = LeaveRequest.objects.exclude(status='pending').order_by('-approved_date')[:5]

    context = {
        'pending_leaves': pending_leaves,
        'history_leaves': history_leaves,
    }
    return render(request, 'hr/manager_dashboard.html', context)

@staff_member_required
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'approved'
    leave.approved_by = request.user
    leave.approved_date = timezone.now()
    leave.save()

    messages.success(request, f'อนุมัติใบลาของ {leave.employee.first_name} เรียบร้อยแล้ว')
    return redirect('manager_dashboard')

@staff_member_required
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'rejected'
    leave.approved_by = request.user
    leave.approved_date = timezone.now()
    leave.save()

    messages.error(request, f'ไม่อนุมัติใบลาของ {leave.employee.first_name}')
    return redirect('manager_dashboard')


# ==========================================
# 5. ส่วนของผู้บริหาร (Executive Zone)
# ==========================================
@staff_member_required(login_url='/login/')
def hr_executive_dashboard(request):
    today = date.today()

    # KPI Data
    total_employees = Employee.objects.count()
    present_count = Attendance.objects.filter(date=today, time_in__isnull=False).count()
    on_leave_today = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today, status='approved').count()
    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    total_commission_paid = CommissionLog.objects.aggregate(Sum('amount'))['amount__sum'] or 0

    dept_data = Employee.objects.values('department__name').annotate(count=Count('id')).order_by('-count')
    new_hires = Employee.objects.order_by('-start_date')[:5]

    context = {
        'total_employees': total_employees,
        'present_count': present_count,
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
        'total_commission_paid': total_commission_paid,
        'dept_data': dept_data,
        'new_hires': new_hires,
    }

    return render(request, 'hr/admin_dashboard.html', context)

# ==========================================
# ✅ 6. ฟังก์ชันลงทะเบียนพนักงานใหม่ (แก้ไข: เพิ่ม Auto ID)
# ==========================================
@staff_member_required(login_url='/login/')
def employee_add(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES) 
        if form.is_valid():
            emp = form.save(commit=False)
            
            # ---------------------------------------------------
            # ✅ 1. สร้างรหัสพนักงานอัตโนมัติ (Auto Generate ID)
            # ---------------------------------------------------
            now = datetime.now()
            prefix = f"EMP-{now.strftime('%y%m')}" # เช่น EMP-2601
            
            # หาพนักงานคนล่าสุดของเดือนนี้
            last_emp = Employee.objects.filter(emp_id__startswith=prefix).order_by('emp_id').last()
            
            if last_emp:
                try:
                    # ตัดเลขท้ายมาบวก 1
                    seq = int(last_emp.emp_id.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            
            # กำหนดรหัสให้พนักงาน
            emp.emp_id = f"{prefix}-{seq:03d}" # เช่น EMP-2601-001
            
            # ---------------------------------------------------
            # 2. สร้าง User Account (ถ้าติ๊กเลือก)
            # ---------------------------------------------------
            create_user = form.cleaned_data.get('create_user_account')
            if create_user:
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                email = form.cleaned_data.get('email')
                
                if username and password:
                    # เช็คก่อนว่า Username ซ้ำไหม
                    if User.objects.filter(username=username).exists():
                        messages.error(request, f"Username '{username}' มีผู้ใช้งานแล้ว กรุณาเปลี่ยนใหม่")
                        return render(request, 'hr/employee_add.html', {'form': form})
                        
                    user = User.objects.create_user(username=username, password=password, email=email)
                    emp.user = user
            
            # บันทึกจริง
            emp.save()
            messages.success(request, f"✅ ลงทะเบียนพนักงาน {emp.first_name} เรียบร้อยแล้ว (รหัส: {emp.emp_id})")
            return redirect('hr_executive_dashboard')
            
    else:
        form = EmployeeForm()

    return render(request, 'hr/employee_add.html', {'form': form})