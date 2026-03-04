from django import forms
from .models import BOM, BOMItem
# 🌟 ดึง Model Category มาใช้ด้วย 🌟
from inventory.models import Product, Category 

class BOMForm(forms.ModelForm):
    # 🌟 เพิ่มฟิลด์จำลอง สำหรับกรองหมวดหมู่ 🌟
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label='ตัวกรอง: หมวดหมู่สินค้า',
        empty_label='--- ทั้งหมด ---',
        widget=forms.Select(attrs={'class': 'form-select shadow-sm text-primary fw-bold', 'id': 'id_category'})
    )

    class Meta:
        model = BOM
        fields = ['product', 'name', 'note']
        labels = {
            'product': 'สินค้าสำเร็จรูป (FG)',
            'name': 'ชื่อสูตรผลิต',
            'note': 'หมายเหตุ'
        }
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select shadow-sm border-primary', 'required': 'required', 'id': 'id_product'}),
            'name': forms.TextInput(attrs={'class': 'form-control shadow-sm', 'placeholder': 'เช่น สูตรมาตรฐาน 1 ห้องนอน', 'required': 'required'}),
            'note': forms.Textarea(attrs={'class': 'form-control shadow-sm', 'rows': 2, 'placeholder': 'รายละเอียดเพิ่มเติม (ถ้ามี)'}),
        }

    def __init__(self, *args, **kwargs):
        super(BOMForm, self).__init__(*args, **kwargs)
        # ดึงเฉพาะ Product ที่เป็นสินค้าสำเร็จรูป (FG)
        self.fields['product'].queryset = Product.objects.filter(product_type='FG', is_active=True)
        
        # 🌟 ถ้านี่คือโหมดแก้ไข (Edit) ให้ดึงหมวดหมู่ของสินค้านั้นมาแสดงอัตโนมัติ 🌟
        if self.instance and self.instance.pk and self.instance.product:
            self.fields['category'].initial = self.instance.product.category

class BOMItemForm(forms.ModelForm):
    class Meta:
        model = BOMItem
        fields = ['raw_material', 'quantity']
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-select shadow-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control shadow-sm text-center', 'step': '0.0001', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super(BOMItemForm, self).__init__(*args, **kwargs)
        # ตัด Product ที่เป็นสินค้าสำเร็จรูป (FG) ออกไป โชว์แค่วัตถุดิบ
        self.fields['raw_material'].queryset = Product.objects.exclude(product_type='FG').filter(is_active=True)

BOMItemFormSet = forms.inlineformset_factory(
    BOM, BOMItem, form=BOMItemForm, extra=1, can_delete=True
)