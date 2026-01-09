from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum
from datetime import datetime, date, timedelta # ✅ Import เพิ่มเติม

from .models import Employee, Attendance, LeaveRequest, Payslip, CommissionLog 
from .forms import LeaveRequestForm

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
    # 1. สลิปเงินเดือนล่าสุด
    latest_payslip = Payslip.objects.filter(employee=employee, status='published').order_by('-year', '-month').first()
    
    # 2. สถานะวันนี้
    today_attendance = Attendance.objects.filter(employee=employee, date=date.today()).first()

    # 3. ประวัติการลา (กรองตามวันที่ หรือ เอามาทั้งหมดก็ได้ - ในที่นี้เอา 5 รายการล่าสุดเหมือนเดิม หรือจะกรองก็ได้)
    # แต่ปกติประวัติลาดูรวมๆ จะดีกว่า เจนี่คงไว้แบบล่าสุด 5 รายการครับ
    leaves = LeaveRequest.objects.filter(employee=employee).order_by('-start_date')[:5]

    # 4. ✅ ประวัติเวลาเข้า-ออก (Attendance Log) - กรองตามช่วงเวลาที่เลือก
    attendance_history = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date_str, end_date_str]
    ).order_by('-date')

    context = {
        'employee': employee,
        'payslip': latest_payslip,
        'leaves': leaves,
        'today_attendance': today_attendance,
        'attendance_history': attendance_history, # ส่งไปหน้าเว็บ
        'start_date': start_date_str,             # ส่งค่ากลับไปแปะในฟอร์ม
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
                messages.success(request, f'ลงเวลาเข้างานเรียบร้อย ({attendance.time_in.strftime("%H:%M")})') # แจ้งเตือน
            
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
                messages.success(request, f'ลงเวลาออกงานเรียบร้อย ({attendance.time_out.strftime("%H:%M")})') # แจ้งเตือน
                
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