from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum
from datetime import datetime, date, timedelta
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Employee, Attendance, LeaveRequest, Payslip, CommissionLog, Position, Department
from .forms import LeaveRequestForm, EmployeeForm

# ==========================================
# 🛡️ ระบบจัดการสิทธิ์ (Permission Checks)
# ==========================================
def is_hr_or_admin(user):
    """เช็กว่าเป็น HR หรือ Admin หรือไม่"""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='HR_Team').exists()

def is_manager_or_hr_or_admin(user):
    """เช็กว่าเป็น ผู้จัดการ, HR หรือ Admin หรือไม่"""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=['Manager_Team', 'HR_Team']).exists()

# ==========================================
# 🟢 1. โซนพนักงานทั่วไป (Employee Zone)
# ==========================================
@login_required(login_url='/login/')
def employee_dashboard(request):
    try:
        employee = request.user.employee
    except AttributeError:
        return render(request, 'hr/error_no_profile.html')

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not start_date_str or not end_date_str:
        today = date.today()
        start_date_str = today.replace(day=1).strftime('%Y-%m-%d')
        end_date_str = today.strftime('%Y-%m-%d')

    latest_payslip = Payslip.objects.filter(employee=employee, status='published').order_by('-year', '-month').first()
    today_attendance = Attendance.objects.filter(employee=employee, date=date.today()).first()
    leaves = LeaveRequest.objects.filter(employee=employee).order_by('-start_date')[:5]

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

@login_required
def payslip_list(request):
    payslips = Payslip.objects.filter(employee=request.user.employee, status='published').order_by('-year', '-month')
    return render(request, 'hr/payslip_list.html', {'payslips': payslips})

@login_required
def payslip_detail(request, payslip_id):
    payslip = get_object_or_404(Payslip, id=payslip_id, employee=request.user.employee)
    return render(request, 'hr/payslip_detail.html', {'payslip': payslip})


# ==========================================
# 🟡 2. โซนหัวหน้างาน (Manager Zone)
# ==========================================
@user_passes_test(is_manager_or_hr_or_admin, login_url='/')
def manager_dashboard(request):
    pending_leaves = LeaveRequest.objects.filter(status='pending').order_by('start_date')
    history_leaves = LeaveRequest.objects.exclude(status='pending').order_by('-approved_date')[:5]
    context = {'pending_leaves': pending_leaves, 'history_leaves': history_leaves}
    return render(request, 'hr/manager_dashboard.html', context)

@user_passes_test(is_manager_or_hr_or_admin, login_url='/')
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'approved'
    leave.approved_by = request.user
    leave.approved_date = timezone.now()
    leave.save()
    messages.success(request, f'อนุมัติใบลาของ {leave.employee.first_name} เรียบร้อยแล้ว')
    return redirect('manager_dashboard')

@user_passes_test(is_manager_or_hr_or_admin, login_url='/')
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'rejected'
    leave.approved_by = request.user
    leave.approved_date = timezone.now()
    leave.save()
    messages.error(request, f'ไม่อนุมัติใบลาของ {leave.employee.first_name}')
    return redirect('manager_dashboard')


# ==========================================
# 🔴 3. โซนฝ่ายบุคคล/ผู้บริหาร (HR/Admin Zone)
# ==========================================
@user_passes_test(is_hr_or_admin, login_url='/')
def hr_executive_dashboard(request):
    today = date.today()
    total_employees = Employee.objects.count()
    present_count = Attendance.objects.filter(date=today, time_in__isnull=False).count()
    on_leave_today = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today, status='approved').count()
    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    total_commission_paid = CommissionLog.objects.aggregate(Sum('amount'))['amount__sum'] or 0

    dept_data = Employee.objects.values('department__name').annotate(count=Count('id')).order_by('-count')
    new_hires = Employee.objects.order_by('-start_date')[:5]

    context = {
        'total_employees': total_employees, 'present_count': present_count,
        'on_leave_today': on_leave_today, 'pending_leaves': pending_leaves,
        'total_commission_paid': total_commission_paid, 'dept_data': dept_data,
        'new_hires': new_hires,
    }
    return render(request, 'hr/admin_dashboard.html', context)

@user_passes_test(is_hr_or_admin, login_url='/')
def employee_add(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            emp = form.save(commit=False)
            now = datetime.now()
            prefix = f"EMP-{now.strftime('%y%m')}"

            last_emp = Employee.objects.filter(emp_id__startswith=prefix).order_by('emp_id').last()
            if last_emp:
                try: seq = int(last_emp.emp_id.split('-')[-1]) + 1
                except ValueError: seq = 1
            else:
                seq = 1

            emp.emp_id = f"{prefix}-{seq:03d}"

            create_user = form.cleaned_data.get('create_user_account')
            if create_user:
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                email = form.cleaned_data.get('email')

                if username and password:
                    if User.objects.filter(username=username).exists():
                        messages.error(request, f"Username '{username}' มีผู้ใช้งานแล้ว กรุณาเปลี่ยนใหม่")
                        return render(request, 'hr/employee_add.html', {'form': form})
                    user = User.objects.create_user(username=username, password=password, email=email)
                    emp.user = user

            emp.save()
            messages.success(request, f"✅ ลงทะเบียนพนักงาน {emp.first_name} เรียบร้อยแล้ว (รหัส: {emp.emp_id})")
            return redirect('hr_executive_dashboard')
    else:
        form = EmployeeForm()
    return render(request, 'hr/employee_add.html', {'form': form})

# ==========================================
# ✏️ ฟังก์ชันสำหรับแก้ไขข้อมูลพนักงาน (Edit)
# ==========================================
@user_passes_test(is_hr_or_admin, login_url='/')
def employee_edit(request, emp_id):
    # ดึงข้อมูลพนักงานคนเดิมขึ้นมา
    employee = get_object_or_404(Employee, emp_id=emp_id)
    
    if request.method == 'POST':
        # ใส่ instance=employee เพื่อบอก Django ว่าเป็นการ "แก้ไข" (Update) ไม่ใช่สร้างใหม่
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            emp = form.save(commit=False)
            
            # ตรวจสอบการสร้าง User Login ใหม่ (กรณีที่ตอนแรกยังไม่มีบัญชี)
            create_user = form.cleaned_data.get('create_user_account')
            if create_user and not emp.user:
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                email = form.cleaned_data.get('email')
                
                if username and password:
                    if User.objects.filter(username=username).exists():
                        messages.error(request, f"Username '{username}' มีผู้ใช้งานแล้ว กรุณาเปลี่ยนใหม่")
                        return render(request, 'hr/employee_edit.html', {'form': form, 'employee': employee})
                    user = User.objects.create_user(username=username, password=password, email=email)
                    emp.user = user
            
            emp.save()
            messages.success(request, f"✅ บันทึกการแก้ไขข้อมูลของ {emp.first_name} เรียบร้อยแล้ว")
            return redirect('role_management') # เซฟเสร็จให้เด้งกลับไปหน้าระบบสิทธิ์
    else:
        # โหลดฟอร์มพร้อมข้อมูลเดิม
        form = EmployeeForm(instance=employee)
        
    return render(request, 'hr/employee_edit.html', {'form': form, 'employee': employee})

@user_passes_test(is_hr_or_admin, login_url='/')
def network_tree(request):
    root_employees = Employee.objects.filter(introducer__isnull=True).order_by('id')
    return render(request, 'hr/network_tree.html', {'root_employees': root_employees})


# ==========================================
# 🚀 API เสริมสำหรับ Quick Add (+) และ Generate
# ==========================================
@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_create_position(request):
    title = request.POST.get('title')
    if title:
        position, created = Position.objects.get_or_create(title=title)
        return JsonResponse({'status': 'success', 'id': position.id, 'title': position.title})
    return JsonResponse({'status': 'error', 'message': 'Missing title'}, status=400)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_create_department(request):
    name = request.POST.get('name')
    if name:
        dept, created = Department.objects.get_or_create(name=name)
        return JsonResponse({'status': 'success', 'id': dept.id, 'name': dept.name})
    return JsonResponse({'status': 'error', 'message': 'Missing name'}, status=400)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_generate_emp_id(request):
    """API สำหรับสร้างรหัสพนักงานล่วงหน้า (กดปุ่มแล้วเด้งมาโชว์)"""
    now = datetime.now()
    prefix = f"EMP-{now.strftime('%y%m')}"
    last_emp = Employee.objects.filter(emp_id__startswith=prefix).order_by('emp_id').last()
    
    if last_emp:
        try: seq = int(last_emp.emp_id.split('-')[-1]) + 1
        except ValueError: seq = 1
    else:
        seq = 1
        
    new_id = f"{prefix}-{seq:03d}"
    return JsonResponse({'status': 'success', 'emp_id': new_id})


# ==========================================
# 🔐 4. โซนจัดการสิทธิ์ (Role Management & Profiles)
# ==========================================
@user_passes_test(is_hr_or_admin, login_url='/')
def role_management(request):
    """
    หน้าจอสำหรับจัดการสิทธิ์ของพนักงานทุกคน
    """
    # ดึงรายชื่อพนักงานทั้งหมด (รวมข้อมูล User และ Group ไว้เลย จะได้โหลดเร็วๆ)
    employees = Employee.objects.select_related('user').prefetch_related('user__groups').order_by('emp_id')

    # ดึงรายชื่อ Group ทั้งหมดที่มีในระบบมาแสดงใน Dropdown
    all_groups = Group.objects.all().order_by('name')

    context = {
        'employees': employees,
        'all_groups': all_groups,
    }
    return render(request, 'hr/role_management.html', context)

@user_passes_test(is_hr_or_admin, login_url='/')
def employee_access_profile(request, emp_id):
    """หน้าจอจัดการสิทธิ์รายบุคคล (เปิดปิดเมนู & รีเซ็ตรหัส)"""
    employee = get_object_or_404(Employee, emp_id=emp_id)
    all_groups = Group.objects.all().order_by('name')
    
    user_groups = []
    if employee.user:
        user_groups = list(employee.user.groups.values_list('id', flat=True))
        
    context = {
        'employee': employee,
        'all_groups': all_groups,
        'user_groups': user_groups,
    }
    return render(request, 'hr/employee_access_profile.html', context)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_update_user_role(request):
    """
    API สำหรับรับค่าจากหน้าเว็บ แล้วไปแก้ไข Group ให้ User อัตโนมัติ (Primary Role Dropdown)
    """
    try:
        user_id = request.POST.get('user_id')
        group_id = request.POST.get('group_id')

        # 1. หา User คนนั้นให้เจอ
        target_user = get_object_or_404(User, id=user_id)

        # 2. ล้างสิทธิ์เก่าออกให้หมดก่อน (รีเซ็ต)
        target_user.groups.clear()

        # 3. ถ้ามีการเลือกสิทธิ์ใหม่ ให้เพิ่มเข้าไป
        if group_id:
            target_group = get_object_or_404(Group, id=group_id)
            target_user.groups.add(target_group)
            role_name = target_group.name
        else:
            role_name = "พนักงานทั่วไป (Employee)"

        return JsonResponse({'status': 'success', 'message': f'อัปเดตสิทธิ์เป็น {role_name} เรียบร้อย'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_create_group(request):
    """API สำหรับสร้างกลุ่มสิทธิ์ใหม่"""
    name = request.POST.get('name')
    if name:
        group, created = Group.objects.get_or_create(name=name)
        return JsonResponse({'status': 'success', 'id': group.id, 'name': group.name})
    return JsonResponse({'status': 'error', 'message': 'Missing name'}, status=400)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_reset_password(request):
    """API รีเซ็ตรหัสผ่าน"""
    user_id = request.POST.get('user_id')
    new_password = request.POST.get('new_password')
    try:
        user = get_object_or_404(User, id=user_id)
        user.set_password(new_password)
        user.save()
        return JsonResponse({'status': 'success', 'message': 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@user_passes_test(is_hr_or_admin, login_url='/')
@require_POST
def api_toggle_user_group(request):
    """API สำหรับเปิด/ปิดสิทธิ์การเข้าถึงเมนู (Toggle Switches)"""
    user_id = request.POST.get('user_id')
    group_id = request.POST.get('group_id')
    action = request.POST.get('action') # รับค่า 'add' หรือ 'remove'
    
    try:
        user = get_object_or_404(User, id=user_id)
        group = get_object_or_404(Group, id=group_id)
        
        if action == 'add':
            user.groups.add(group)
        elif action == 'remove':
            user.groups.remove(group)
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)