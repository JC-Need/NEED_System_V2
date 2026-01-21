from django import forms
from .models import StockMovement, Product

# ==========================================
# 1. ฟอร์มรับสินค้าเข้า (Stock In) - ✅ ปรับปรุงใหม่
# ==========================================
class StockInForm(forms.ModelForm):
    # เพิ่มช่องกรอกข้อมูลหัวเอกสาร (ไม่ผูกกับ Model โดยตรง)
    doc_reference = forms.CharField(required=False, label="อ้างอิงเอกสาร (PO)", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น PO-2601-001'}))
    doc_note = forms.CharField(required=False, label="หมายเหตุ", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'รายละเอียดเพิ่มเติม...'}))

    class Meta:
        model = StockMovement
        fields = ['product', 'quantity'] # เอาเฉพาะข้อมูลสินค้า
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'จำนวนที่รับ'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].label = "เลือกสินค้า/วัตถุดิบ"

# ==========================================
# 2. ฟอร์มเบิกสินค้าออก (Stock Out) - ✅ ปรับปรุงใหม่
# ==========================================
class StockOutForm(forms.ModelForm):
    doc_reference = forms.CharField(required=False, label="อ้างอิงเอกสาร (Job No.)", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น ใบสั่งผลิต / ใบเสีย'}))
    doc_note = forms.CharField(required=False, label="หมายเหตุ", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'สาเหตุการเบิก...'}))

    class Meta:
        model = StockMovement
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'จำนวนที่เบิก'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].label = "เลือกสินค้า/วัตถุดิบ"

# ==========================================
# 3. ฟอร์มจัดการสินค้า (ProductForm) - (คงเดิม)
# ==========================================
class ProductForm(forms.ModelForm):
    cost_price = forms.CharField(label="ราคาทุน", widget=forms.TextInput(attrs={'class': 'form-control number-input', 'style': 'text-align: right;', 'placeholder': '0.00'}))
    sell_price = forms.CharField(label="ราคาขาย", widget=forms.TextInput(attrs={'class': 'form-control number-input', 'style': 'text-align: right;', 'placeholder': '0.00'}))

    class Meta:
        model = Product
        fields = ['product_type', 'code', 'name', 'category', 'cost_price', 'sell_price', 'min_level', 'image', 'is_active']
        widgets = {
            'product_type': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เว้นว่างเพื่อสร้างรหัสอัตโนมัติ'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select select2'}),
            'min_level': forms.NumberInput(attrs={'class': 'form-control', 'value': 5}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False 
        
        if self.instance.pk:
            if self.instance.cost_price: self.initial['cost_price'] = f"{self.instance.cost_price:,.2f}"
            if self.instance.sell_price: self.initial['sell_price'] = f"{self.instance.sell_price:,.2f}"
        else:
            self.initial['cost_price'] = '0.00'
            self.initial['sell_price'] = '0.00'

    def clean_cost_price(self):
        return self.cleaned_data['cost_price'].replace(',', '') if self.cleaned_data['cost_price'] else 0
    
    def clean_sell_price(self):
        return self.cleaned_data['sell_price'].replace(',', '') if self.cleaned_data['sell_price'] else 0