from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum  # ✅ เพิ่ม Sum
import datetime

# ✅ เพิ่ม CommissionLog
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

    latest_payslip = Payslip.objects.filter(employee=employee, status='published').order_by('-year', '-month').first()
    recent_leaves = LeaveRequest.objects.filter(employee=employee).order_by('-start_date')[:5]
    today_attendance = Attendance.objects.filter(employee=employee, date=datetime.date.today()).first()

    context = {
        'employee': employee,
        'payslip': latest_payslip,
        'leaves': recent_leaves,
        'today_attendance': today_attendance,
        'current_date': timezone.now(),
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
            today = datetime.date.today()
            attendance, created = Attendance.objects.get_or_create(employee=employee, date=today)
            
            if not attendance.time_in:
                attendance.time_in = timezone.localtime(timezone.now()).time()
                attendance.save()
                
        except Exception as e:
            print(f"Error checking in: {e}")
            
    return redirect('employee_dashboard')

@login_required
def check_out(request):
    if request.method == 'POST':
        try:
            employee = request.user.employee
            today = datetime.date.today()
            attendance = Attendance.objects.filter(employee=employee, date=today).first()
            
            if attendance:
                attendance.time_out = timezone.localtime(timezone.now()).time()
                attendance.save()
                
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
# 4. ส่วนของผู้จัดการ (Manager Zone - Operational)
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
# 5. ส่วนของผู้บริหาร (Executive Zone - Analytics)
# ==========================================
@staff_member_required(login_url='/login/')
def hr_executive_dashboard(request):
    today = datetime.date.today()
    
    # KPI 1: ข้อมูลพื้นฐาน
    total_employees = Employee.objects.count()
    present_count = Attendance.objects.filter(date=today, time_in__isnull=False).count()
    on_leave_today = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today, status='approved').count()
    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    
    # ✅ KPI 2 (ใหม่): ยอดจ่ายคอมมิชชั่นรวมทั้งบริษัท (ถ้ายังไม่มีให้เป็น 0)
    total_commission_paid = CommissionLog.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # KPI 3: ข้อมูลกราฟ
    dept_data = Employee.objects.values('department__name').annotate(count=Count('id')).order_by('-count')
    new_hires = Employee.objects.order_by('-start_date')[:5]
    
    context = {
        'total_employees': total_employees,
        'present_count': present_count,
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
        'total_commission_paid': total_commission_paid, # ✅ ส่งตัวเลขไปหน้าบ้าน
        'dept_data': dept_data,
        'new_hires': new_hires,
    }
    
    return render(request, 'hr/admin_dashboard.html', context)