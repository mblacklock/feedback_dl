from django.test import TestCase
from django.urls import resolve, reverse
from feedback.views import home
from feedback.models import AssessmentTemplate

class HomeViewTest(TestCase):
    def test_root_url_resolves_to_home_view(self):
        match = resolve("/feedback/")
        assert match.func == home

    def test_home_renders_template_with_title(self):
        resp = self.client.get("/feedback/")
        assert resp.status_code == 200
        assert b"Welcome to the Feedback Portal" in resp.content
        assert b"<title>Feedback</title>" in resp.content

class TemplateBuilderViewTests(TestCase):
    def test_get_new_template_creates_template_and_redirects_to_edit(self):
        """GET /feedback/template/new/ creates a template and redirects to edit page."""
        url = reverse("template_new")
        res = self.client.get(url, follow=False)
        self.assertEqual(res.status_code, 302)
        # Should redirect to edit page
        self.assertTrue(res.url.endswith('/edit/'))
        
        # Follow the redirect
        res = self.client.get(url, follow=True)
        self.assertEqual(res.status_code, 200)
        # Should show edit page with fields
        self.assertContains(res, 'name="title"')
        self.assertContains(res, 'name="module_code"')
        self.assertContains(res, 'name="assessment_title"')
        self.assertContains(res, 'id="categories"')
        self.assertContains(res, 'id="add-category"')
        self.assertContains(res, 'id="save-status"')
        self.assertContains(res, 'id="view-template"')

    def test_post_valid_creates_template_and_redirects_to_summary(self):
        """POST valid data creates a template with categories (in order) and redirects to summary."""
        url = reverse("template_new")
        payload = {
            "title": "KB5031 – FEA Coursework",
            "module_code": "KB5031",
            "assessment_title": "Coursework 1: Truss Analysis",
            # dynamic rows submitted as parallel arrays
            "category_label": ["Introduction", "Method", "Design"],
            "category_max": ["10", "20", "10"],
        }
        res = self.client.post(url, data=payload, follow=False)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(AssessmentTemplate.objects.count(), 1)

        tpl = AssessmentTemplate.objects.first()
        self.assertEqual(tpl.title, payload["title"])
        self.assertEqual(tpl.module_code, "KB5031")
        self.assertEqual(tpl.assessment_title, "Coursework 1: Truss Analysis")
        self.assertEqual(
            tpl.categories,
            [
                {"label": "Introduction", "max": 10, "type": "numeric"},
                {"label": "Method", "max": 20, "type": "numeric"},
                {"label": "Design", "max": 10, "type": "numeric"},
            ],
        )

        # Follow to summary page
        summary_url = reverse("template_summary", args=[tpl.id])
        res2 = self.client.get(summary_url)
        self.assertEqual(res2.status_code, 200)
        self.assertContains(res2, "KB5031 – FEA Coursework")
        # Category list shown in order
        for lab in ["Introduction", "Method", "Design"]:
            self.assertContains(res2, f">{lab}<")

    def test_post_requires_at_least_one_category(self):
        """Submitting without any non-empty categories returns form errors and does not save."""
        url = reverse("template_new")
        payload = {
            "title": "Empty Cats",
            "module_code": "KB0000",
            "assessment_title": "Test",
            "category_label": [""],  # empty
            "category_max": [""],
        }
        res = self.client.post(url, data=payload)
        self.assertEqual(res.status_code, 200)  # stays on form
        self.assertContains(res, "At least one category is required")
        self.assertEqual(AssessmentTemplate.objects.count(), 0)

    def test_post_rejects_blank_labels_and_bad_max(self):
        """Invalid category rows (blank label, non-numeric or out of range max) produce errors and no save."""
        url = reverse("template_new")
        payload = {
            "title": "Invalid Cats",
            "module_code": "KB9999",
            "assessment_title": "Bad Data",
            "category_label": ["", "Method", "Design"],
            "category_max": ["10", "not-a-number", "-1"],
        }
        res = self.client.post(url, data=payload)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Category labels cannot be blank")
        self.assertContains(res, "Max marks must be a number between 1 and 1000")
        self.assertEqual(AssessmentTemplate.objects.count(), 0)

    def test_post_requires_title_module_code_and_assessment_title(self):
        """Title, module_code, and assessment_title cannot be blank."""
        url = reverse("template_new")
        payload = {
            "title": "",
            "module_code": "",
            "assessment_title": "",
            "category_label": ["Introduction"],
            "category_max": ["10"],
        }
        res = self.client.post(url, data=payload)
        self.assertEqual(res.status_code, 200)  # stays on form
        self.assertContains(res, "Title is required")
        self.assertContains(res, "Module code is required")
        self.assertContains(res, "Assessment title is required")
        self.assertEqual(AssessmentTemplate.objects.count(), 0)

    def test_post_creates_category_with_grade_bands(self):
        """POST with grade type and subdivision creates category with those fields."""
        url = reverse("template_new")
        payload = {
            "title": "Grade Bands Template",
            "module_code": "KB5031",
            "assessment_title": "Test",
            "category_label": ["Comprehension", "Method"],
            "category_max": ["30", "20"],
            "category_type": ["grade", "numeric"],
            "category_subdivision": ["high_low", ""],  # only grade types have subdivision
        }
        res = self.client.post(url, data=payload, follow=False)
        self.assertEqual(res.status_code, 302)
        
        tpl = AssessmentTemplate.objects.first()
        self.assertEqual(len(tpl.categories), 2)
        
        # First category has grade bands
        self.assertEqual(tpl.categories[0]["label"], "Comprehension")
        self.assertEqual(tpl.categories[0]["max"], 30)
        self.assertEqual(tpl.categories[0]["type"], "grade")
        self.assertEqual(tpl.categories[0]["subdivision"], "high_low")
        
        # Second category is numeric (no subdivision)
        self.assertEqual(tpl.categories[1]["label"], "Method")
        self.assertEqual(tpl.categories[1]["max"], 20)
        self.assertEqual(tpl.categories[1]["type"], "numeric")
        self.assertNotIn("subdivision", tpl.categories[1])
    
    def test_post_rejects_grade_subdivision_that_would_create_cross_band_violations(self):
        """POST with grade type + subdivision that would create cross-band violations is rejected."""
        url = reverse("template_new")
        payload = {
            "title": "Invalid Grade Bands",
            "module_code": "KB5031",
            "assessment_title": "Test",
            "category_label": ["Very Low Marks"],
            "category_max": ["5"],
            "category_type": ["grade"],
            "category_subdivision": ["none"],  # 5 marks can't represent all grade bands
        }
        res = self.client.post(url, data=payload)
        self.assertEqual(res.status_code, 200)  # stays on form
        self.assertContains(res, "5 marks is too low for subdivision")
        self.assertEqual(AssessmentTemplate.objects.count(), 0)

class GradeBandsPreviewTests(TestCase):
    def test_grade_bands_preview_returns_html_for_valid_params(self):
        """GET /feedback/grade-bands-preview/ returns rendered HTML."""
        url = reverse("grade_bands_preview")
        res = self.client.get(url, {"max_marks": "30", "subdivision": "high_low"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/json")
        
        import json
        data = json.loads(res.content)
        self.assertIn("html", data)
        self.assertIsInstance(data["html"], str)
        self.assertGreater(len(data["html"]), 0)
        
        # Check that HTML contains expected grade information
        html = data["html"]
        self.assertIn("1st", html)
        self.assertIn("card", html)
        self.assertIn("grade-description", html)
    
    def test_grade_bands_preview_returns_correct_grades_for_none_subdivision(self):
        """Preview endpoint returns HTML with correct grades for 'none' subdivision."""
        url = reverse("grade_bands_preview")
        res = self.client.get(url, {"max_marks": "10", "subdivision": "none"})
        
        import json
        data = json.loads(res.content)
        html = data["html"]
        
        # Check for expected grade names in HTML
        self.assertIn("Maximum 1st", html)
        self.assertIn("High 1st", html)
        self.assertIn("2:1", html)
        self.assertIn("Zero Fail", html)
    
    def test_grade_bands_preview_returns_empty_for_invalid_marks(self):
        """Preview endpoint returns empty HTML for invalid marks."""
        url = reverse("grade_bands_preview")
        res = self.client.get(url, {"max_marks": "0", "subdivision": "none"})
        
        import json
        data = json.loads(res.content)
        self.assertEqual(data["html"], "")
    
    def test_grade_bands_preview_returns_empty_for_missing_params(self):
        """Preview endpoint returns empty HTML when params are missing."""
        url = reverse("grade_bands_preview")
        res = self.client.get(url)
        
        import json
        data = json.loads(res.content)
        self.assertEqual(data["html"], "")
