from django import forms
from .models import StockMovement, Product

# ==========================================
# 1. ฟอร์มรับสินค้าเข้า (Stock In)
# ==========================================
class StockInForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'reference_doc', 'note']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'ระบุจำนวนที่รับเข้า'}),
            'reference_doc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น PO-2601-001'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'รายละเอียดเพิ่มเติม...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].label = "เลือกสินค้าที่รับเข้า"

# ==========================================
# 2. ฟอร์มเบิกสินค้าออก (Stock Out)
# ==========================================
class StockOutForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'reference_doc', 'note']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'ระบุจำนวนที่เบิก'}),
            'reference_doc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น ใบเบิกผลิต / ใบเสีย'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'สาเหตุการเบิก...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].label = "เลือกสินค้าที่จะเบิก"

# ==========================================
# 3. ฟอร์มจัดการสินค้า (ProductForm) - ✅ ปรับปรุงล่าสุด
# ==========================================
class ProductForm(forms.ModelForm):
    # 1️⃣ เปลี่ยนเป็น CharField เพื่อให้พิมพ์ลูกน้ำ (,) ได้
    cost_price = forms.CharField(
        label="ราคาทุน",
        widget=forms.TextInput(attrs={
            'class': 'form-control number-input',  # เพิ่ม class พิเศษ
            'style': 'text-align: right;',         # ชิดขวา
            'placeholder': '0.00'
        })
    )
    sell_price = forms.CharField(
        label="ราคาขาย",
        widget=forms.TextInput(attrs={
            'class': 'form-control number-input',
            'style': 'text-align: right;',
            'placeholder': '0.00'
        })
    )

    class Meta:
        model = Product
        fields = ['code', 'name', 'category', 'cost_price', 'sell_price', 'min_level', 'image', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น P-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ระบุชื่อสินค้า'}),
            'category': forms.Select(attrs={'class': 'form-select select2'}),
            'min_level': forms.NumberInput(attrs={'class': 'form-control', 'value': 5}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].label = "หมวดหมู่สินค้า"
        self.fields['is_active'].label = "เปิดใช้งานสินค้านี้ทันที"

        # 2️⃣ ถ้าเป็นการแก้ไข (Edit) ให้จัดรูปแบบตัวเลขมีลูกน้ำรอไว้เลย
        if self.instance.pk:
            if self.instance.cost_price:
                self.initial['cost_price'] = f"{self.instance.cost_price:,.2f}"
            if self.instance.sell_price:
                self.initial['sell_price'] = f"{self.instance.sell_price:,.2f}"
        else:
            # ถ้าสร้างใหม่ ให้เป็นค่าว่างหรือ 0.00 ตามต้องการ
            self.initial['cost_price'] = '0.00'
            self.initial['sell_price'] = '0.00'

    # 3️⃣ ฟังก์ชันล้างลูกน้ำ (,) ออกก่อนบันทึกลง Database
    def clean_cost_price(self):
        price = self.cleaned_data['cost_price']
        if price:
            return price.replace(',', '') # ลบลูกน้ำออก
        return 0

    def clean_sell_price(self):
        price = self.cleaned_data['sell_price']
        if price:
            return price.replace(',', '') # ลบลูกน้ำออก
        return 0