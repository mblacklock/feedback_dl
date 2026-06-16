from django.contrib import admin
from .models import ThemeConfig

@admin.register(ThemeConfig)
class ThemeConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "brand_primary", "brand_accent")
    list_filter = ("is_active",)
    search_fields = ("name",)
