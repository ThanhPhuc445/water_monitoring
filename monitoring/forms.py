from django import forms
from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = [
            'title',
            'report_type',
            'device',
            'readings',
            'forecasts',
            'content',
            'status',
            'created_by_name',
            'location'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tiêu đề báo cáo...'
            }),
            'report_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'readings': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'forecasts': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Nhập nội dung chi tiết của báo cáo...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'created_by_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tên người tạo...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập vị trí...'
            }),
        }
