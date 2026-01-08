from django import forms
from .models import Employee, Position, Department
from django.contrib.auth.models import User

class EmployeeOnboardingForm(forms.ModelForm):
    # ✅ ส่วนเสริม: สร้าง User Login ทันที
    create_user_account = forms.BooleanField(required=False, initial=True, label="สร้างบัญชีผู้ใช้งานทันที")
    username = forms.CharField(required=False, label="ชื่อเข้าระบบ (Username)", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น somchai.j'}))
    password = forms.CharField(required=False, label="รหัสผ่าน (Password)", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ตั้งรหัสผ่าน...'}))
    email = forms.EmailField(required=False, label="อีเมล (Email)", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@company.com'}))

    class Meta:
        model = Employee
        fields = [
            'prefix', 'first_name', 'last_name', 'nickname', 'gender', 'birth_date', 'photo',
            'phone', 'address', 
            # ❌ ตัด 'user' ออก เพราะเราจะสร้างให้เองใน Views
            'position', 'department', 'salary', 'start_date',
            'introducer', 'business_rank', 'commission_rate',
            'bank_name', 'bank_account'
        ]
        
        widgets = {
            'prefix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น คุณ'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'birth_date': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'วว/ดด/ปปปป'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            
            # ✅ ใส่ ID ให้ชัดเจน (สำหรับ JS ยิงค่ากลับมาใส่ตอนกดปุ่ม +)
            'position': forms.Select(attrs={'class': 'form-select', 'id': 'id_position'}),
            'department': forms.Select(attrs={'class': 'form-select', 'id': 'id_department'}),
            
            'salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'วว/ดด/ปปปป'}),
            
            'introducer': forms.Select(attrs={'class': 'form-select'}),
            'business_rank': forms.Select(attrs={'class': 'form-select'}),
            'commission_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น กสิกรไทย'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(EmployeeOnboardingForm, self).__init__(*args, **kwargs)
        self.fields['introducer'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name} ({obj.business_rank})"
        self.fields['introducer'].empty_label = "🌟 ติดตัวบริษัท (ไม่มีผู้แนะนำ)"