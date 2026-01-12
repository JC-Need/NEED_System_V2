from django import forms
from django.core.validators import RegexValidator # ✅ เพิ่มตัวช่วยตรวจสอบ
from .models import Quotation

class QuotationForm(forms.ModelForm):
    # --- ส่วนที่ 1: ตั้งค่าปฏิทิน ---
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control datepicker', 'placeholder': 'วว/ดด/ปปปป'}),
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )
    valid_until = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control datepicker', 'placeholder': 'วว/ดด/ปปปป'}),
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )

    # --- ส่วนที่ 2: เพิ่มกฎเหล็ก (Validation) ---
    
    # ✅ เบอร์โทร: บังคับกรอก (required=True) + ต้องเป็นตัวเลข 9-10 หลัก ขึ้นต้นด้วย 0
    customer_phone = forms.CharField(
        label="เบอร์โทรศัพท์",
        required=True,
        validators=[RegexValidator(r'^0\d{8,9}$', 'เบอร์โทรต้องเป็นตัวเลข 9-10 หลัก (เช่น 081xxxxxxx)')],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ตัวอย่าง: 0812345678'})
    )

    # ✅ Tax ID: ไม่บังคับ (required=False) + แต่ถ้าใส่ ต้องเป็นเลข 13 หลักเท่านั้น
    customer_tax_id = forms.CharField(
        label="เลขผู้เสียภาษี",
        required=False,
        validators=[RegexValidator(r'^\d{13}$', 'เลขผู้เสียภาษีต้องเป็นตัวเลข 13 หลัก')],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ระบุเลข 13 หลัก (ถ้ามี)'})
    )

    class Meta:
        model = Quotation
        fields = ['date', 'valid_until', 'customer_name', 'customer_tax_id', 'customer_phone', 'customer_address', 'note']
        widgets = {
            # ชื่อลูกค้าห้ามว่าง
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'ระบุชื่อลูกค้า...'}),
            'customer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    # ด่านสุดท้าย: เช็คชื่อลูกค้าอีกรอบ
    def clean_customer_name(self):
        name = self.cleaned_data.get('customer_name')
        if not name:
            raise forms.ValidationError("กรุณาระบุชื่อลูกค้า")
        return name