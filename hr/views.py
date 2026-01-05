from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Employee, Attendance, LeaveRequest, Payslip
from django.utils import timezone
import datetime

@login_required(login_url='/login/') # บังคับว่าต้องล็อกอินก่อน
def employee_dashboard(request):
    try:
        # 1. ดึงข้อมูลพนักงานของคนที่ล็อกอินอยู่ (My Profile)
        employee = request.user.employee
    except AttributeError:
        # กรณี User นี้ยังไม่ได้ผูกกับ Employee Profile ให้เด้งออกไปก่อน
        return render(request, 'hr/error_no_profile.html')

    # 2. ดึงข้อมูลสลิปเงินเดือนล่าสุด (My Salary)
    current_year = datetime.date.today().year
    current_month = datetime.date.today().month
    
    # พยายามหาสลิปเดือนนี้ ถ้าไม่มีให้เอาเดือนล่าสุดที่มี
    latest_payslip = Payslip.objects.filter(employee=employee, status='published').order_by('-year', '-month').first()

    # 3. ดึงประวัติการลา (My Leaves) - เอาแค่ 5 รายการล่าสุด
    recent_leaves = LeaveRequest.objects.filter(employee=employee).order_by('-start_date')[:5]

    # 4. ดึงประวัติการลงเวลา (My Attendance) - เอาแค่วันนี้
    today_attendance = Attendance.objects.filter(employee=employee, date=datetime.date.today()).first()

    context = {
        'employee': employee,
        'payslip': latest_payslip,
        'leaves': recent_leaves,
        'today_attendance': today_attendance,
        'current_date': timezone.now(),
    }
    
    return render(request, 'hr/dashboard.html', context)