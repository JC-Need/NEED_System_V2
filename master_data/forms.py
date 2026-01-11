from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['code', 'created_at', 'updated_at'] # รหัสสร้างเอง ไม่ต้องกรอก
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'zip_code': forms.TextInput(attrs={'id': 'input_zipcode'}),
            'location': forms.TextInput(attrs={'id': 'input_location', 'placeholder': 'กดปุ่มเพื่อดึงพิกัด GPS'}),
            'phone': forms.TextInput(attrs={'id': 'input_phone', 'placeholder': '0xx-xxx-xxxx'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_active':
                self.fields[field].widget.attrs.update({'class': 'form-control'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input ms-2'})