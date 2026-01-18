from django import forms
from django.core.exceptions import ValidationError
from .models import Customer

class CustomerForm(forms.ModelForm):
    # เบอร์โทรศัพท์ (มี Auto-Clean + ปิดประวัติ)
    phone = forms.CharField(
        label="เบอร์โทรศัพท์",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'input_phone',
            'placeholder': 'ตัวอย่าง: 0812345678 (ระบบจะตัดขีดออกให้อัตโนมัติ)',
            'autocomplete': 'off'  # ✅ ปิดประวัติ
        })
    )

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['code', 'created_at', 'updated_at', 'credit_limit', 'credit_term']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'ระบุชื่อลูกค้า / บริษัท', 
                'autocomplete': 'off' # ✅ ปิดประวัติ
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'เลขผู้เสียภาษี 13 หลัก', 
                'autocomplete': 'off' # ✅ ปิดประวัติ
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'ระบุชื่อผู้ติดต่อ', 
                'autocomplete': 'off' # ✅ ปิดประวัติ
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2, 
                'autocomplete': 'off' # ✅ ปิดประวัติ
            }),
            'note': forms.Textarea(attrs={'rows': 3}),
            'zip_code': forms.TextInput(attrs={'id': 'input_zipcode', 'autocomplete': 'off'}),
            'location': forms.TextInput(attrs={'id': 'input_location', 'placeholder': 'กดปุ่มเพื่อดึงพิกัด GPS', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_active':
                self.fields[field].widget.attrs.update({'class': 'form-control'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input ms-2'})

    def clean_phone(self):
        data = self.cleaned_data['phone']
        if not data:
            return data
        cleaned_data = data.replace('-', '').replace(' ', '')
        if not cleaned_data.isdigit():
            raise ValidationError("เบอร์โทรต้องเป็นตัวเลขเท่านั้น")
        if len(cleaned_data) != 10:
            raise ValidationError(f"เบอร์โทรต้องมี 10 หลัก (ตอนนี้มี {len(cleaned_data)} หลัก)")
        return cleaned_data