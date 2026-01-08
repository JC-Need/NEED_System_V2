from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .forms_employee import EmployeeOnboardingForm  # ✅ เรียกใช้ฟอร์มใหม่ที่เราเพิ่งสร้าง

@staff_member_required
def employee_create(request):
    if request.method == 'POST':
        # รับข้อมูลทั้งข้อความ (POST) และรูปภาพ (FILES)
        form = EmployeeOnboardingForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save()
            
            # แจ้งเตือนสวยๆ
            messages.success(request, f'🎉 ยินดีต้อนรับ! คุณ {employee.first_name} เข้าสู่ทีมเรียบร้อยแล้ว')
            
            # บันทึกเสร็จ กลับไปหน้า HR Analytics
            return redirect('hr_executive_dashboard')
    else:
        # เปิดหน้าเว็บครั้งแรก สร้างฟอร์มเปล่าๆ
        form = EmployeeOnboardingForm()
    
    return render(request, 'hr/employee_add.html', {'form': form})