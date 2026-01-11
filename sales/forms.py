from django import forms
from .models import Quotation

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            'date', 'valid_until', 'customer_name', 
            'customer_tax_id', 'customer_phone', 
            'customer_address', 'note'
        ]
        widgets = {
            # ✅ เปลี่ยน widget เป็น DateInput แบบกำหนด Format เอง (dd/mm/yyyy)
            # และใส่ class 'datepicker' เพื่อให้ JavaScript รู้จัก
            'date': forms.DateInput(
                format='%d/%m/%Y', 
                attrs={'class': 'form-control datepicker', 'placeholder': 'dd/mm/yyyy'}
            ),
            'valid_until': forms.DateInput(
                format='%d/%m/%Y', 
                attrs={'class': 'form-control datepicker', 'placeholder': 'dd/mm/yyyy'}
            ),
            
            # ส่วนอื่นๆ เหมือนเดิม
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_customer_name', 'placeholder': 'ระบุชื่อลูกค้า'}),
            'customer_tax_id': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_customer_tax_id'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_customer_phone'}),
            'customer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'id_customer_address'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ บังคับให้ Django ยอมรับวันที่แบบ dd/mm/yyyy
        self.fields['date'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
        self.fields['valid_until'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']