from django import forms
from django.core.exceptions import ValidationError # ✅ 1. Import ตัวแจ้ง Error เพิ่ม
from .models import Customer

class CustomerForm(forms.ModelForm):
    # ✅ 2. เอา RegexValidator ออก เพื่อรับค่าที่มีขีดได้ (แล้วค่อยไปลบทีหลัง)
    phone = forms.CharField(
        label="เบอร์โทรศัพท์",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'input_phone',
            'placeholder': 'ตัวอย่าง: 0812345678 (ระบบจะตัดขีดออกให้อัตโนมัติ)', # ปรับข้อความให้เป็นมิตรขึ้น
            'autocomplete': 'new-password'
        })
    )

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['code', 'created_at', 'updated_at', 'credit_limit', 'credit_term']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ระบุชื่อลูกค้า / บริษัท', 'autocomplete': 'new-password'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เลขผู้เสียภาษี 13 หลัก', 'autocomplete': 'new-password'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ระบุชื่อผู้ติดต่อ', 'autocomplete': 'new-password'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'autocomplete': 'new-password'}),
            'note': forms.Textarea(attrs={'rows': 3}),
            'zip_code': forms.TextInput(attrs={'id': 'input_zipcode'}),
            'location': forms.TextInput(attrs={'id': 'input_location', 'placeholder': 'กดปุ่มเพื่อดึงพิกัด GPS'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_active':
                self.fields[field].widget.attrs.update({'class': 'form-control'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input ms-2'})

    # ✅ 3. เพิ่มฟังก์ชัน "ล้างข้อมูลเบอร์โทร" (Auto-Clean Logic)
    def clean_phone(self):
        data = self.cleaned_data['phone']
        if not data:
            return data

        # ลบขีด (-) และช่องว่าง ( ) ออกให้หมด
        cleaned_data = data.replace('-', '').replace(' ', '')

        # ตรวจสอบว่าเป็นตัวเลขล้วนหรือไม่
        if not cleaned_data.isdigit():
            raise ValidationError("เบอร์โทรต้องเป็นตัวเลขเท่านั้น")

        # ตรวจสอบความยาว (ต้อง 10 หลัก)
        if len(cleaned_data) != 10:
            raise ValidationError(f"เบอร์โทรต้องมี 10 หลัก (ตอนนี้มี {len(cleaned_data)} หลัก)")

        return cleaned_data

    def clean_tax_id(self):
        data = self.cleaned_data.get('tax_id')
        if not data:
            return data

        # ลบขีดและช่องว่างออกให้หมด
        cleaned_data = data.replace('-', '').replace(' ', '')

        # ตรวจสอบว่าเป็นตัวเลขล้วน
        if not cleaned_data.isdigit():
            raise ValidationError("เลขผู้เสียภาษีต้องเป็นตัวเลขเท่านั้น")

        # ตรวจสอบความยาว (13 หลัก)
        if len(cleaned_data) != 13:
            raise ValidationError(f"เลขผู้เสียภาษีต้องมี 13 หลัก (ตอนนี้มี {len(cleaned_data)} หลัก)")

        return cleaned_data