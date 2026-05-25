from django.contrib import admin
from .models import FeedbackRow

@admin.register(FeedbackRow)
class FeedbackRowAdmin(admin.ModelAdmin):
    list_display = ('order', 'label', 'text_positive_preview', 'text_negative_preview')
    ordering = ('order',)

    def text_positive_preview(self, obj):
        return obj.text_positive[:50] + "..." if len(obj.text_positive) > 50 else obj.text_positive
    
    def text_negative_preview(self, obj):
        return obj.text_negative[:50] + "..." if len(obj.text_negative) > 50 else obj.text_negative
