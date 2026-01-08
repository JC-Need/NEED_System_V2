from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse 
from django.views.decorators.http import require_POST
from .models import Employee, Position, Department
from .forms_employee import EmployeeOnboardingForm

@staff_member_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeOnboardingForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. เตรียมข้อมูลพนักงาน (ยังไม่ Save)
            employee = form.save(commit=False)
            
            # 2. ตรวจสอบเงื่อนไขสร้าง User
            if form.cleaned_data.get('create_user_account'):
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                email = form.cleaned_data.get('email')
                
                if username and password:
                    # เช็คซ้ำว่าชื่อซ้ำไหม
                    if User.objects.filter(username=username).exists():
                        messages.error(request, 'ชื่อผู้ใช้งาน (Username) นี้มีอยู่แล้ว โปรดเปลี่ยนชื่อใหม่')
                        return render(request, 'hr/employee_add.html', {'form': form})
                    
                    # สร้าง User ใหม่
                    try:
                        new_user = User.objects.create_user(username=username, password=password, email=email)
                        employee.user = new_user # ผูก User เข้ากับพนักงานทันที
                        messages.success(request, f'สร้างบัญชีผู้ใช้ {username} เรียบร้อยแล้ว')
                    except Exception as e:
                        messages.error(request, f'เกิดข้อผิดพลาดในการสร้าง User: {e}')

            # 3. บันทึกข้อมูลพนักงานจริง
            employee.save()
            messages.success(request, f'🎉 ยินดีต้อนรับ! คุณ {employee.first_name} เข้าสู่ทีมเรียบร้อยแล้ว')
            return redirect('hr_executive_dashboard')
    else:
        form = EmployeeOnboardingForm()
    
    return render(request, 'hr/employee_add.html', {'form': form})

# ==========================================
# 🚀 API สำหรับสร้างข้อมูลด่วน (Quick Add)
# ==========================================

@staff_member_required
@require_POST
def api_create_position(request):
    """API: รับค่าชื่อตำแหน่ง แล้วสร้างลง Database ทันที"""
    title = request.POST.get('title')
    if title:
        position, created = Position.objects.get_or_create(title=title)
        return JsonResponse({'status': 'success', 'id': position.id, 'title': position.title})
    return JsonResponse({'status': 'error', 'message': 'Missing title'}, status=400)

@staff_member_required
@require_POST
def api_create_department(request):
    """API: รับค่าชื่อแผนก แล้วสร้างลง Database ทันที"""
    name = request.POST.get('name')
    if name:
        dept, created = Department.objects.get_or_create(name=name)
        return JsonResponse({'status': 'success', 'id': dept.id, 'name': dept.name})
    return JsonResponse({'status': 'error', 'message': 'Missing name'}, status=400)