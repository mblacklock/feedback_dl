from django.test import TestCase
from django.urls import resolve
from feedback.views import home

class HomeViewTest(TestCase):
    def test_root_url_resolves_to_home_view(self):
        match = resolve("/feedback/")
        assert match.func == home

    def test_home_renders_template_with_title(self):
        resp = self.client.get("/feedback/")
        assert resp.status_code == 200
        assert b"Welcome to the Feedback Portal" in resp.content
        assert b"<title>Feedback</title>" in resp.content
