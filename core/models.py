from django.db import models

class ThemeConfig(models.Model):
    name = models.CharField(max_length=100, default="Default Theme", unique=True)
    is_active = models.BooleanField(default=False)
    
    # CSS Custom Property Variables (storing hex colors like #1a1a2e)
    brand_primary = models.CharField(max_length=7, default="#1a1a2e", help_text="Hex color code (e.g. #1a1a2e)")
    brand_primary_dark = models.CharField(max_length=7, default="#0f172a", help_text="Hex color code (e.g. #0f172a)")
    brand_primary_light = models.CharField(max_length=7, default="#2e2e4a", help_text="Hex color code (e.g. #2e2e4a)")
    brand_accent = models.CharField(max_length=7, default="#c8a951", help_text="Hex color code (e.g. #c8a951)")

    def save(self, *args, **kwargs):
        if self.is_active:
            # Mark all other configurations as inactive
            ThemeConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Active)" if self.is_active else self.name

    @classmethod
    def get_active(cls):
        try:
            theme = cls.objects.filter(is_active=True).first()
            if not theme:
                # Return a transient/in-memory instance with the default colors
                theme = cls(
                    name="Default Theme",
                    is_active=True,
                    brand_primary="#1a1a2e",
                    brand_primary_dark="#0f172a",
                    brand_primary_light="#2e2e4a",
                    brand_accent="#c8a951",
                )
            return theme
        except Exception:
            # Safe fallback if database isn't fully migrated yet during startup or tests
            return cls(
                name="Default Theme",
                is_active=True,
                brand_primary="#1a1a2e",
                brand_primary_dark="#0f172a",
                brand_primary_light="#2e2e4a",
                brand_accent="#c8a951",
            )
