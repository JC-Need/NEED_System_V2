from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import ProductionOrder, BOM
from master_data.models import CompanyInfo

@login_required
def production_print(request, po_id):
    # 1. ดึงใบสั่งผลิต
    po = get_object_or_404(ProductionOrder, id=po_id)
    
    # 2. หาสูตรการผลิต (BOM) ของสินค้านี้ เพื่อเอามาโชว์รายการวัตถุดิบ
    bom = BOM.objects.filter(product=po.product).first()
    
    # 3. ข้อมูลบริษัท
    company = CompanyInfo.objects.first()
    
    context = {
        'po': po,
        'bom': bom,      # ส่งสูตรไปที่หน้าจอ
        'company': company,
    }
    return render(request, 'manufacturing/production_print.html', context)