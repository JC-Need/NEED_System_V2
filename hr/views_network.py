from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Employee

@staff_member_required
def network_tree(request):
    # 1. ดึงเฉพาะ "ต้นสาย" (Root Nodes) คือคนที่เป็นจุดเริ่มต้น (ไม่มีใครแนะนำ)
    # ส่วนลูกทีม (Downlines) เราจะใช้ความสามารถของ Database ดึงต่อกันไปเรื่อยๆ ในหน้าจอครับ
    root_employees = Employee.objects.filter(introducer__isnull=True).order_by('id')
    
    context = {
        'root_employees': root_employees
    }
    return render(request, 'hr/network_tree.html', context)