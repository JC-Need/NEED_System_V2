from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
from .models import SolarJob, SolarExpense
from .forms import SolarJobForm, SolarMaterialFormSet, SolarExpenseForm
from master_data.models import Customer

# 🌟 ดึงตารางสินค้าจากแผนกโซล่าเซลล์โดยตรง
from solar_sales.models import SolarProduct

# ------------------------------------------
# 🛡️ ระบบเช็คสิทธิ์สำหรับแผนก Center / ปฏิบัติการ
# ------------------------------------------
def is_center_staff(user):
    if user.is_superuser: return True
    if hasattr(user, 'employee') and user.employee:
        dept = getattr(user.employee.department, 'name', '')
        # 🌟 เพิ่มคำว่า 'ปฏิบัติการ' เข้าไปในเงื่อนไขการตรวจจับสิทธิ์
        if 'Center' in dept or 'Manager' in dept or 'บริหาร' in dept or 'ปฏิบัติการ' in dept:
            return True
    return False

@login_required
def center_dashboard(request):
    if not is_center_staff(request.user):
        messages.error(request, "❌ บัญชีของคุณไม่มีสิทธิ์เข้าถึงระบบ Center (Solar)")
        return redirect('dashboard')

    # ดึงข้อมูลงานทั้งหมด
    all_jobs = SolarJob.objects.all().order_by('-created_at')

    # สรุปตัวเลขสำหรับแสดงบนการ์ดด้านบน
    draft_jobs = all_jobs.filter(status='DRAFT').count()
    preparing_jobs = all_jobs.filter(status='PREPARING').count()
    in_progress_jobs = all_jobs.filter(status='IN_PROGRESS').count()
    pending_expenses = SolarExpense.objects.filter(status='PENDING').count()

    context = {
        'jobs': all_jobs[:20], # ดึงมาโชว์ 20 งานล่าสุด
        'draft_jobs': draft_jobs,
        'preparing_jobs': preparing_jobs,
        'in_progress_jobs': in_progress_jobs,
        'pending_expenses': pending_expenses,
    }
    return render(request, 'solar_jobs/center_dashboard.html', context)

@login_required
def solar_job_create(request):
    if not is_center_staff(request.user): return redirect('solar_center_dashboard')

    # ฟังก์ชันสำหรับสร้างงานด่วนเพื่อทดสอบระบบ (จำลองว่าเซลส์ขายงานมา)
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        package_id = request.POST.get('package_id')

        customer = Customer.objects.filter(id=customer_id).first()
        # 🌟 เปลี่ยนมาใช้ SolarProduct
        package = SolarProduct.objects.filter(id=package_id).first()

        job = SolarJob.objects.create(
            customer=customer,
            package_sold=package,
            status='DRAFT'
        )
        messages.success(request, f"✅ สร้างใบสั่งงาน {job.code} เรียบร้อยแล้ว ระบบกำลังพาไปหน้าจัดการงาน")
        return redirect('solar_job_manage', job_id=job.id)

    # ดึงข้อมูลลูกค้าและสินค้าไปแสดงใน Popup
    customers = Customer.objects.all()
    # 🌟 กรองเอาเฉพาะแพ็กเกจ (FG)
    packages = SolarProduct.objects.filter(is_active=True, product_type='FG')

    return render(request, 'solar_jobs/job_create_modal.html', {'customers': customers, 'packages': packages})

@login_required
def solar_job_manage(request, job_id):
    if not is_center_staff(request.user): return redirect('solar_center_dashboard')

    job = get_object_or_404(SolarJob, id=job_id)

    if request.method == 'POST':
        form = SolarJobForm(request.POST, instance=job)
        formset = SolarMaterialFormSet(request.POST, instance=job)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ บันทึกข้อมูลการจัดทีมและเบิกวัตถุดิบของงาน {job.code} เรียบร้อยแล้ว")
            return redirect('solar_center_dashboard')
        else:
            messages.error(request, "❌ กรุณาตรวจสอบข้อมูลให้ครบถ้วน")
    else:
        form = SolarJobForm(instance=job)
        formset = SolarMaterialFormSet(instance=job)

    # 🌟 ส่งข้อมูลวัตถุดิบ (RM) ไปให้ Formset เลือกเท่านั้น
    raw_materials = SolarProduct.objects.filter(is_active=True, product_type='RM')

    return render(request, 'solar_jobs/job_manage.html', {
        'job': job,
        'form': form,
        'formset': formset,
        'raw_materials': raw_materials
    })

# ------------------------------------------
# 🛡️ ระบบเช็คสิทธิ์สำหรับแผนกบัญชี
# ------------------------------------------
def is_accounting_staff(user):
    if user.is_superuser: return True
    if hasattr(user, 'employee') and user.employee:
        dept = getattr(user.employee.department, 'name', '')
        if 'บัญชี' in dept or 'Accounting' in dept: return True
    return False

# ------------------------------------------
# 💸 ระบบตั้งเบิกค่าใช้จ่าย (Expenses)
# ------------------------------------------
@login_required
def expense_list(request):
    # ดึงรายการเบิกทั้งหมด
    expenses = SolarExpense.objects.all().order_by('-created_at')

    # ถ้าไม่ใช่บัญชี หรือ Center ให้เห็นแค่รายการของตัวเองเท่านั้น
    if not (is_accounting_staff(request.user) or is_center_staff(request.user)):
        expenses = expenses.filter(requester=getattr(request.user, 'employee', None))

    is_accounting = is_accounting_staff(request.user)

    return render(request, 'solar_jobs/expense_list.html', {
        'expenses': expenses,
        'is_accounting': is_accounting
    })

@login_required
def expense_create(request):
    if request.method == 'POST':
        form = SolarExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.requester = getattr(request.user, 'employee', None)
            exp.save()
            messages.success(request, f"✅ ส่งเรื่องตั้งเบิกยอด {exp.amount:,.2f} บาท เรียบร้อยแล้ว (รอฝ่ายบัญชีตรวจสอบ)")
            return redirect('solar_expense_list')
        else:
            messages.error(request, "❌ กรุณาตรวจสอบข้อมูลให้ครบถ้วน")
    else:
        # กำหนดค่าเริ่มต้น ถ้าระบุรหัสงานมาใน URL
        initial_job = request.GET.get('job_id')
        form = SolarExpenseForm(initial={'job': initial_job} if initial_job else None)

    return render(request, 'solar_jobs/expense_form.html', {'form': form})

@login_required
def expense_approve(request, expense_id):
    # ป้องกันไม่ให้แผนกอื่นกดอนุมัติ
    if not is_accounting_staff(request.user):
        messages.error(request, "❌ เฉพาะพนักงานฝ่ายบัญชีเท่านั้นที่สามารถอนุมัติการจ่ายเงินได้")
        return redirect('solar_expense_list')

    expense = get_object_or_404(SolarExpense, id=expense_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            expense.status = 'APPROVED'
            expense.approved_by = getattr(request.user, 'employee', None)
            messages.success(request, f"✅ อนุมัติการเบิกจ่ายยอด {expense.amount:,.2f} บาท เรียบร้อยแล้ว")
        elif action == 'reject':
            expense.status = 'REJECTED'
            messages.warning(request, f"⚠️ ปฏิเสธรายการตั้งเบิกของ {expense.requester.first_name if expense.requester else 'พนักงาน'}")
        expense.save()

    return redirect('solar_expense_list')