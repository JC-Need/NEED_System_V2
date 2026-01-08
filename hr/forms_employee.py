from django import forms
from .models import Employee
from django.contrib.auth.models import User

class EmployeeOnboardingForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            # ข้อมูลส่วนตัว
            'prefix', 'first_name', 'last_name', 'nickname', 'gender', 'birth_date', 'photo',
            
            # ข้อมูลติดต่อ & User
            'phone', 'address', 'user',
            
            # ข้อมูลงาน & เงินเดือน
            'position', 'department', 'salary', 'start_date',
            
            # 🌳 ส่วนโครงสร้างทีม (ใหม่)
            'introducer',      # เลือกหัวหน้าทีม
            'business_rank',   # ระดับตำแหน่ง
            'commission_rate', # % คอมมิชชั่น
            'bank_name', 'bank_account' # บัญชีรับเงิน
        ]
        
        widgets = {
            'prefix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น นาย/นาง/นางสาว'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'birth_date': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'วว/ดด/ปปปป'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'user': forms.Select(attrs={'class': 'form-select'}),
            
            'position': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'วว/ดด/ปปปป'}),
            
            # 🌳 Widgets สำหรับส่วน Network
            'introducer': forms.Select(attrs={'class': 'form-select'}),
            'business_rank': forms.Select(attrs={'class': 'form-select'}),
            'commission_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น กสิกรไทย'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(EmployeeOnboardingForm, self).__init__(*args, **kwargs)
        # ปรับการแสดงผลชื่อหัวหน้าทีมให้ชัดเจน (ชื่อ + ตำแหน่ง)
        self.fields['introducer'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name} ({obj.business_rank})"
        # เพิ่มตัวเลือก "ไม่มีผู้แนะนำ (ติดตัวบริษัท)"
        self.fields['introducer'].empty_label = "🌟 ติดตัวบริษัท (ไม่มีผู้แนะนำ)"