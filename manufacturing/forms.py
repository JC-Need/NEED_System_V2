from django import forms
from .models import BOM, BOMItem

class BOMForm(forms.ModelForm):
    class Meta:
        model = BOM
        fields = ['product', 'name', 'note']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น สูตรมาตรฐาน'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class BOMItemForm(forms.ModelForm):
    class Meta:
        model = BOMItem
        fields = ['raw_material', 'quantity']
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
        }

# Formset สำหรับจัดการรายการวัตถุดิบในสูตรผลิต
BOMItemFormSet = forms.inlineformset_factory(
    BOM, BOMItem, form=BOMItemForm, extra=1, can_delete=True
)