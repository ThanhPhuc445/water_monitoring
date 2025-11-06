from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css):
    """
    Thêm class CSS cho field trong form (khi render template).
    Nếu field không hợp lệ, trả về chính field (không lỗi).
    """
    try:
        return field.as_widget(attrs={'class': css})
    except Exception:
        return mark_safe(field)
