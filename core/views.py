from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
import datetime

# Import เพื่อนบ้าน
from sales.models import POSOrder
from inventory.models import Product
from purchasing.models import PurchaseOrder
from accounting.models import Income, Expense

@login_required
def dashboard(request):
    today = datetime.date.today()
    
    # 1. ยอดขายวันนี้
    sales_today = POSOrder.objects.filter(created_at__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # 2. สินค้าใกล้หมด
    low_stock_count = Product.objects.filter(stock_qty__lte=F('min_level'), is_active=True).count()
    
    # 3. PO รอรับของ
    pending_po_count = PurchaseOrder.objects.filter(status='ORDERED').count()
    
    # 4. การเงินเดือนนี้
    current_month = today.month
    current_year = today.year
    income_month = Income.objects.filter(date__month=current_month, date__year=current_year).aggregate(Sum('amount'))['amount__sum'] or 0
    expense_month = Expense.objects.filter(date__month=current_month, date__year=current_year).aggregate(Sum('amount'))['amount__sum'] or 0
    profit_month = income_month - expense_month

    context = {
        'sales_today': sales_today,
        'low_stock_count': low_stock_count,
        'pending_po_count': pending_po_count,
        'income_month': income_month,
        'expense_month': expense_month,
        'profit_month': profit_month,
    }
    return render(request, 'core/dashboard.html', context)