from django import template
from django.contrib.staticfiles import finders
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def inline_static(path):
    """
    Finds a static file and returns its raw text content.
    Used for inlining CSS directly inside HTML templates to generate self-contained sheets.
    """
    file_path = finders.find(path)
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return mark_safe(f.read())
        except IOError:
            return f"/* Error reading static file: {path} */"
    return f"/* Error: Static file not found: {path} */"

