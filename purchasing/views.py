from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import PurchaseOrder
from master_data.models import CompanyInfo

@login_required
def po_print(request, po_id):
    # 1. ดึงใบสั่งซื้อตาม ID
    po = get_object_or_404(PurchaseOrder, id=po_id)
    
    # 2. ดึงข้อมูลบริษัท (เอาโลโก้/ที่อยู่ไปแปะหัวบิล)
    company = CompanyInfo.objects.first()
    
    context = {
        'po': po,
        'company': company,
        'items': po.items.all() # ดึงรายการสินค้าใน PO
    }
    return render(request, 'purchasing/po_print.html', context)