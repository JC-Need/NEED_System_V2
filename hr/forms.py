from django import forms
from .models import LeaveRequest
from django.core.exceptions import ValidationError
import datetime

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            
            # ✅ แก้ไขเด็ดขาด: ใช้ TextInput เพื่อบังคับให้เป็นช่องข้อความธรรมดา
            # Browser จะไม่เข้ามายุ่ง และจะโชว์ Placeholder ของเรา 100%
            'start_date': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'dd/mm/yyyy (เช่น 31/01/2026)',
                'autocomplete': 'off' # ปิดการจำค่าเก่า เพื่อให้เห็น Placeholder ชัดๆ
            }),
            
            'end_date': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'dd/mm/yyyy (เช่น 31/01/2026)',
                'autocomplete': 'off'
            }),
            
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ระบุเหตุผลการลา...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        # ตรวจสอบว่าวันที่ถูกต้องหรือไม่ (เพราะตอนนี้เราให้กรอกเป็น Text ระบบจึงต้องเช็คละเอียดขึ้น)
        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError("วันสิ้นสุดต้องไม่ก่อนวันที่เริ่มต้น")
        return cleaned_data