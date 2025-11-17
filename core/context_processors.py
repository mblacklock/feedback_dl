from django.conf import settings

def global_settings(request):
    return {
        'RUBRIC_MODE': settings.RUBRIC_MODE,
        # add as many as you like
    }
