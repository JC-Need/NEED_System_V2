from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from .models import Income, Expense

# นำเข้าโมเดลจากแอปอื่นเพื่อดึงยอด "งานด่วนรอตรวจสอบ"
from sales.models import POSOrder, Invoice
from purchasing.models import PurchaseOrder

@login_required
def accounting_dashboard(request):
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year

    # 1. คำนวณรายรับ-รายจ่าย เฉพาะเดือนปัจจุบัน
    incomes = Income.objects.filter(date__month=current_month, date__year=current_year)
    expenses = Expense.objects.filter(date__month=current_month, date__year=current_year)

    total_income = incomes.aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    net_balance = total_income - total_expense

    # 2. นับจำนวนงานด่วนข้ามแผนก (Pending Tasks)
    # ฝ่ายขาย: บิลที่รอตรวจสอบยอดเงินเข้า
    pending_sales = Invoice.objects.filter(status='PENDING').count() + POSOrder.objects.filter(status='PENDING').count()
    # ฝ่ายจัดซื้อ: PO ที่รอโอนเงิน (เฉพาะที่ผู้จัดการอนุมัติแล้ว)
    pending_purchases = PurchaseOrder.objects.filter(status='APPROVED', payment_status__in=['PENDING', 'DEPOSIT']).count()

    # 3. ดึงรายการเคลื่อนไหวล่าสุด 10 รายการ (เงินเข้า/เงินออก ล่าสุด)
    recent_incomes = list(Income.objects.all().order_by('-date', '-id')[:5])
    recent_expenses = list(Expense.objects.all().order_by('-date', '-id')[:5])
    
    # แปะป้ายบอกประเภท เพื่อให้นำไปแสดงสีใน HTML ได้ถูกต้อง
    for i in recent_incomes: i.type = 'income'
    for e in recent_expenses: e.type = 'expense'

    # รวมและเรียงลำดับตามวันที่ (ใหม่ล่าสุดขึ้นก่อน)
    recent_transactions = sorted(recent_incomes + recent_expenses, key=lambda x: x.date, reverse=True)[:10]

    context = {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_balance': net_balance,
        'pending_sales': pending_sales,
        'pending_purchases': pending_purchases,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'accounting/dashboard.html', context)