from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Customer, Province, Amphure, Tambon
from .forms import CustomerForm

# --- Customer Management ---

@login_required
def customer_list(request):
    search = request.GET.get('search', '')

    # 1. ค้นหาข้อมูล (Search Logic)
    if search:
        customer_list = Customer.objects.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(phone__icontains=search) |
            Q(tax_id__icontains=search)
        ).order_by('-created_at')
    else:
        customer_list = Customer.objects.all().order_by('-created_at')

    # 2. ระบบแบ่งหน้า (Pagination Logic)
    paginator = Paginator(customer_list, 20) # แสดงหน้าละ 20 รายการ
    page = request.GET.get('page')

    try:
        customers = paginator.page(page)
    except PageNotAnInteger:
        customers = paginator.page(1)
    except EmptyPage:
        customers = paginator.page(paginator.num_pages)

    return render(request, 'master_data/customer/customer_list.html', {
        'customers': customers, 
        'search': search
    })

@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            cust = form.save()
            messages.success(request, f"เพิ่มลูกค้า {cust.name} เรียบร้อย")
            return redirect('customer_list')
    else:
        form = CustomerForm()

    return render(request, 'master_data/customer/customer_form.html', {'form': form, 'title': 'เพิ่มลูกค้าใหม่'})

@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกข้อมูลเรียบร้อย")
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'master_data/customer/customer_form.html', {'form': form, 'title': 'แก้ไขข้อมูลลูกค้า'})

@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    messages.success(request, "ลบข้อมูลเรียบร้อย")
    return redirect('customer_list')

# --- Address API ---

@login_required
def get_provinces(request):
    provinces = list(Province.objects.values('id', 'name_th').order_by('name_th'))
    return JsonResponse(provinces, safe=False)

@login_required
def get_amphures(request):
    province_id = request.GET.get('province_id')
    amphures = []
    if province_id:
        amphures = list(Amphure.objects.filter(province_id=province_id).values('id', 'name_th').order_by('name_th'))
    return JsonResponse(amphures, safe=False)

@login_required
def get_tambons(request):
    amphure_id = request.GET.get('amphure_id')
    tambons = []
    if amphure_id:
        tambons = list(Tambon.objects.filter(amphure_id=amphure_id).values('id', 'name_th', 'zip_code').order_by('name_th'))
    return JsonResponse(tambons, safe=False)