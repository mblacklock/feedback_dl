from django.conf import settings
from core.models import ThemeConfig

def global_settings(request):
    return {
        'RUBRIC_MODE': settings.RUBRIC_MODE,
        'active_theme': ThemeConfig.get_active(),
    }
