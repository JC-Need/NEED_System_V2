from django import forms
from .models import BOM, BOMItem

class BOMForm(forms.ModelForm):
    class Meta:
        model = BOM
        fields = ['product', 'name', 'note']
        labels = {
            'product': 'สินค้าสำเร็จรูป (FG)',
            'name': 'ชื่อสูตรผลิต',
            'note': 'หมายเหตุ'
        }
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select shadow-sm', 'required': 'required'}),
            'name': forms.TextInput(attrs={'class': 'form-control shadow-sm', 'placeholder': 'เช่น สูตรมาตรฐานบ้าน 1 ห้องนอน', 'required': 'required'}),
            'note': forms.Textarea(attrs={'class': 'form-control shadow-sm', 'rows': 2, 'placeholder': 'รายละเอียดเพิ่มเติม (ถ้ามี)'}),
        }

class BOMItemForm(forms.ModelForm):
    class Meta:
        model = BOMItem
        fields = ['raw_material', 'quantity']
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-select shadow-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control shadow-sm text-center', 'step': '0.0001', 'min': '0'}),
        }

# Formset สำหรับจัดการรายการวัตถุดิบแบบเพิ่มบรรทัดได้
BOMItemFormSet = forms.inlineformset_factory(
    BOM, BOMItem, form=BOMItemForm, extra=1, can_delete=True
)