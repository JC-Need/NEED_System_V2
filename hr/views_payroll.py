from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Payslip

# ==========================================
# 💰 ส่วนจัดการเงินเดือนและสลิป (Payroll System)
# ==========================================

@login_required
def payslip_list(request):
    """
    แสดงรายการสลิปเงินเดือนทั้งหมดของพนักงานคนนั้น
    """
    # ดึงเฉพาะสลิปที่ 'อนุมัติแล้ว' (published) เรียงจากเดือนล่าสุดไปหาเก่า
    payslips = Payslip.objects.filter(
        employee=request.user.employee,
        status='published'
    ).order_by('-year', '-month')

    return render(request, 'hr/payslip_list.html', {'payslips': payslips})

# (อนาคตสามารถเพิ่มฟังก์ชัน export_pdf หรือ calculate_tax ที่นี่ได้เลย ไม่กระทบไฟล์อื่น)

@login_required
def payslip_detail(request, payslip_id):
    """
    แสดงรายละเอียดสลิปเงินเดือน 1 ใบ (เฉพาะของตัวเองเท่านั้น)
    """
    # ดึงสลิปตาม ID และต้องเป็นของพนักงานคนนี้เท่านั้น (ห้ามแอบดูของคนอื่น)
    payslip = get_object_or_404(Payslip, id=payslip_id, employee=request.user.employee)

    return render(request, 'hr/payslip_detail.html', {'payslip': payslip})