from django.test import TestCase, Client
from django.urls import reverse
from core.models import ThemeConfig

class ThemeConfigModelTests(TestCase):
    def test_get_active_fallback(self):
        """If no theme is created or active, get_active() returns the fallback default theme."""
        theme = ThemeConfig.get_active()
        self.assertEqual(theme.name, "Default Theme")
        self.assertEqual(theme.brand_primary, "#1a1a2e")
        self.assertEqual(theme.brand_accent, "#c8a951")
        self.assertTrue(theme.is_active)

    def test_active_theme_singleton_behavior(self):
        """Activating one theme automatically deactivates all other custom themes."""
        t1 = ThemeConfig.objects.create(name="Theme 1", is_active=True, brand_primary="#111111")
        t2 = ThemeConfig.objects.create(name="Theme 2", is_active=True, brand_primary="#222222")

        # Refresh from DB
        t1.refresh_from_db()
        t2.refresh_from_db()

        self.assertFalse(t1.is_active)
        self.assertTrue(t2.is_active)

        # Check get_active returns Theme 2
        active = ThemeConfig.get_active()
        self.assertEqual(active.name, "Theme 2")

    def test_deactivate_all(self):
        """Deactivating themes returns to the fallback default theme."""
        ThemeConfig.objects.create(name="Custom Theme", is_active=True, brand_primary="#333333")
        self.assertEqual(ThemeConfig.get_active().name, "Custom Theme")

        ThemeConfig.objects.update(is_active=False)
        self.assertEqual(ThemeConfig.get_active().name, "Default Theme")


class ThemeConfigViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("theme_settings")

    def test_get_settings_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Theme Settings & Customizer")
        self.assertContains(response, "System Default Theme")

    def test_post_create_theme(self):
        response = self.client.post(self.url, {
            "action": "create",
            "name": "Forest Green",
            "brand_primary": "#0f5132",
            "brand_primary_dark": "#051b11",
            "brand_primary_light": "#198754",
            "brand_accent": "#badbcc",
        })
        self.assertRedirects(response, self.url)
        
        # Verify theme was created
        theme = ThemeConfig.objects.get(name="Forest Green")
        self.assertEqual(theme.brand_primary, "#0f5132")
        self.assertEqual(theme.brand_accent, "#badbcc")
        self.assertFalse(theme.is_active)

    def test_post_activate_theme(self):
        theme = ThemeConfig.objects.create(
            name="Warm Red",
            brand_primary="#842029",
            brand_accent="#f8d7da",
            is_active=False
        )
        
        response = self.client.post(self.url, {
            "action": "activate",
            "theme_id": theme.id
        })
        self.assertRedirects(response, self.url)
        
        theme.refresh_from_db()
        self.assertTrue(theme.is_active)
        self.assertEqual(ThemeConfig.get_active().name, "Warm Red")

    def test_post_deactivate_all_themes(self):
        ThemeConfig.objects.create(
            name="Purple",
            brand_primary="#563d7c",
            is_active=True
        )
        
        response = self.client.post(self.url, {
            "action": "deactivate"
        })
        self.assertRedirects(response, self.url)
        self.assertFalse(ThemeConfig.objects.filter(is_active=True).exists())
        self.assertEqual(ThemeConfig.get_active().name, "Default Theme")

    def test_post_delete_theme(self):
        theme = ThemeConfig.objects.create(name="Delete Me")
        response = self.client.post(self.url, {
            "action": "delete",
            "theme_id": theme.id
        })
        self.assertRedirects(response, self.url)
        self.assertFalse(ThemeConfig.objects.filter(pk=theme.id).exists())
