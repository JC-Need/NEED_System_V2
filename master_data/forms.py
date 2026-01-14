from django import forms
from django.core.validators import RegexValidator # ✅ 1. เพิ่มตัวช่วยตรวจสอบ
from .models import Customer

class CustomerForm(forms.ModelForm):
    # ✅ 2. สร้างกฎเหล็กให้ "เบอร์โทรศัพท์"
    phone = forms.CharField(
        label="เบอร์โทรศัพท์",
        required=False, 
        # บังคับเลข 10 หลัก (^\d{10}$) เท่านั้น
        validators=[RegexValidator(r'^\d{10}$', 'เบอร์โทรต้องเป็นตัวเลข 10 หลักติดกัน (เช่น 0812345678)')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'input_phone',
            'placeholder': 'ห้ามเว้น ใส่เฉพาะตัวเลขเท่านั้น', # ✅ เปลี่ยนข้อความตามสั่ง
            'autocomplete': 'new-password' # ✅ ปิดประวัติ
        })
    )

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['code', 'created_at', 'updated_at'] 
        
        # ✅ 3. ปิดประวัติ (Autocomplete) ให้ครบทุกช่องที่วงมา
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ระบุชื่อลูกค้า / บริษัท', 
                'autocomplete': 'new-password' # 👈 ปิดประวัติ
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'เลขผู้เสียภาษี 13 หลัก', 
                'autocomplete': 'new-password' # 👈 ปิดประวัติ
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ระบุชื่อผู้ติดต่อ', 
                'autocomplete': 'new-password' # 👈 ปิดประวัติ
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2, 
                'autocomplete': 'new-password' # 👈 ปิดประวัติ
            }),
            
            # ส่วนอื่นๆ คงเดิม
            'note': forms.Textarea(attrs={'rows': 3}),
            'zip_code': forms.TextInput(attrs={'id': 'input_zipcode'}),
            'location': forms.TextInput(attrs={'id': 'input_location', 'placeholder': 'กดปุ่มเพื่อดึงพิกัด GPS'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # วนลูปเพื่อใส่ class form-control ให้มั่นใจ (แต่ไม่ทับ widget ที่เราประกาศข้างบน)
        for field in self.fields:
            if field != 'is_active':
                existing_attrs = self.fields[field].widget.attrs
                existing_attrs.update({'class': 'form-control'})
                
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input ms-2'})