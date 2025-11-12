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
        assert b"Feedback Templates" in resp.content
        assert b"<title>Feedback</title>" in resp.content
    
    def test_home_shows_empty_state_when_no_templates(self):
        """Home page shows empty state when no templates exist"""
        resp = self.client.get("/feedback/")
        assert resp.status_code == 200
        assert b"No templates yet" in resp.content
        assert b"Create your first feedback template" in resp.content
    
    def test_home_lists_all_templates(self):
        """Home page lists all templates in a list group"""
        # Create test templates
        template1 = AssessmentTemplate.objects.create(
            component=1,
            title="Template 1",
            module_code="CS101",
            module_title="Computer Science 101",
            assessment_title="Assignment 1",
            weighting=40,
            max_marks=100,
            categories=[{"label": "Content", "max": 10}]
        )
        template2 = AssessmentTemplate.objects.create(
            component=1,
            title="Template 2",
            module_code="CS202",
            module_title="Computer Science 202",
            assessment_title="Exam",
            weighting=60,
            max_marks=150,
            categories=[{"label": "Quality", "max": 20}, {"label": "Style", "max": 10}]
        )
        
        resp = self.client.get("/feedback/")
        assert resp.status_code == 200
        
        # Check for template titles
        assert b"Template 1" in resp.content
        assert b"Template 2" in resp.content
        
        # Check for module codes, components, and assessments
        assert b"CS101" in resp.content
        assert b"Assignment 1" in resp.content
        assert b"CS202" in resp.content
        assert b"Exam" in resp.content
        
        # Check for component display
        assert b"Component:" in resp.content
        assert b"1" in resp.content  # Component value
        
        # Check for category counts
        assert b"1 category" in resp.content
        assert b"2 categories" in resp.content
        
        # Check for View and Edit buttons
        assert f'/feedback/template/{template1.pk}/'.encode() in resp.content
        assert f'/feedback/template/{template1.pk}/edit/'.encode() in resp.content
        assert f'/feedback/template/{template2.pk}/'.encode() in resp.content
        assert f'/feedback/template/{template2.pk}/edit/'.encode() in resp.content
        
        # Check for Delete buttons with data-template-id attributes
        assert f'data-template-id="{template1.pk}"'.encode() in resp.content
        assert f'data-template-id="{template2.pk}"'.encode() in resp.content
        assert b'delete-template' in resp.content  # Check for delete button class

class TemplateDeleteViewTests(TestCase):
    def test_post_delete_removes_template_and_returns_json(self):
        """POST /feedback/template/<pk>/delete/ removes the template and returns JSON."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="To Delete",
            module_code="DEL101",
            module_title="Deletion Module",
            assessment_title="Delete Test",
            weighting=50,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_delete", args=[template.pk])
        resp = self.client.post(url)
        
        # Should return 200 with JSON
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "deleted")
        
        # Template should be deleted
        self.assertEqual(AssessmentTemplate.objects.filter(pk=template.pk).count(), 0)
    
    def test_get_delete_not_allowed(self):
        """GET /feedback/template/<pk>/delete/ is not allowed (only POST)."""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="To Delete",
            module_code="DEL101",
            module_title="Deletion Module",
            assessment_title="Delete Test",
            weighting=50,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_delete", args=[template.pk])
        resp = self.client.get(url)
        
        # Should return 405 Method Not Allowed
        self.assertEqual(resp.status_code, 405)

class TemplateUpdateViewTests(TestCase):
    def test_get_edit_page_shows_home_button(self):
        """GET /feedback/template/<pk>/edit/ shows Back to Home button."""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="KB5031",
            module_title="Test Module",
            assessment_title="Test",
            weighting=40,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_edit", args=[template.pk])
        resp = self.client.get(url)
        
        self.assertEqual(resp.status_code, 200)
        # Check for Back to Home button
        self.assertContains(resp, 'Back to Home')
        self.assertContains(resp, 'href="/feedback/"')
        # Check for View Rubric and View Feedback Sheet buttons
        self.assertContains(resp, 'View Rubric')
        self.assertContains(resp, 'View Feedback Sheet')
    
    def test_post_update_saves_weighting_field(self):
        """POST /feedback/template/<pk>/update/ saves the weighting field."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="KB5031",
            module_title="Test Module",
            assessment_title="Test",
            weighting=30,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_update", args=[template.pk])
        data = {
            "title": "Test Template",
            "module_code": "KB5031",
            "assessment_title": "Test",
            "component": 1,
            "weighting": 50,
            "categories": [{"label": "Test", "max": 10}]
        }
        
        resp = self.client.post(url, data=json.dumps(data), content_type="application/json")
        
        # Should return 200 with success
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content)
        self.assertEqual(result["status"], "saved")
        
        # Template should be updated
        template.refresh_from_db()
        self.assertEqual(template.weighting, 50)
    
    def test_post_update_saves_max_marks_field(self):
        """POST /feedback/template/<pk>/update/ saves the max_marks field."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="KB5031",
            module_title="Test Module",
            assessment_title="Test",
            weighting=40,
            max_marks=80,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_update", args=[template.pk])
        data = {
            "title": "Test Template",
            "module_code": "KB5031",
            "assessment_title": "Test",
            "component": 1,
            "max_marks": 100,
            "categories": [{"label": "Test", "max": 10}]
        }
        
        resp = self.client.post(url, data=json.dumps(data), content_type="application/json")
        
        # Should return 200 with success
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content)
        self.assertEqual(result["status"], "saved")
        
        # Template should be updated
        template.refresh_from_db()
        self.assertEqual(template.max_marks, 100)
    
    def test_post_update_saves_module_title_field(self):
        """POST /feedback/template/<pk>/update/ saves the module_title field."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="KB5031",
            module_title="Old Title",
            assessment_title="Test",
            weighting=40,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_update", args=[template.pk])
        data = {
            "title": "Test Template",
            "module_code": "KB5031",
            "module_title": "Finite Element Analysis",
            "assessment_title": "Test",
            "component": 1,
            "categories": [{"label": "Test", "max": 10}]
        }
        
        resp = self.client.post(url, data=json.dumps(data), content_type="application/json")
        
        # Should return 200 with success
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content)
        self.assertEqual(result["status"], "saved")
        
        # Template should be updated
        template.refresh_from_db()
        self.assertEqual(template.module_title, "Finite Element Analysis")
    
    def test_post_update_saves_component_field(self):
        """POST /feedback/template/<pk>/update/ saves the component field."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="KB5031",
            module_title="Test Module",
            assessment_title="Test",
            weighting=40,
            max_marks=100,
            categories=[{"label": "Test", "max": 10}]
        )
        
        url = reverse("template_update", args=[template.pk])
        data = {
            "title": "Updated Title",
            "module_code": "KB5031",
            "assessment_title": "Test",
            "component": 2,
            "categories": [{"label": "Test", "max": 10}]
        }
        
        resp = self.client.post(url, data=json.dumps(data), content_type="application/json")
        
        # Should return 200 with success
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content)
        self.assertEqual(result["status"], "saved")
        
        # Template should be updated
        template.refresh_from_db()
        self.assertEqual(template.component, 2)
        self.assertEqual(template.title, "Updated Title")

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
        self.assertContains(res, 'View Rubric')
        self.assertContains(res, 'View Feedback Sheet')

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
        self.assertIn("Max 1st", html)
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


class TemplateSeparateViewsTest(TestCase):
    """Test that staff can view rubric and feedback sheet separately"""
    
    def test_template_rubric_view_shows_grade_bands(self):
        """Rubric view shows categories with grade bands"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Software Engineering",
            module_code="CS301",
            module_title="Advanced Software",
            assessment_title="CW1",
            weighting=40,
            max_marks=50,
            categories=[
                {
                    "label": "Design",
                    "max": 30,
                    "type": "grade",
                    "subdivision": "high_low",
                    "grade_band_descriptions": {
                        "1st": "Excellent design"
                    }
                },
                {
                    "label": "Testing",
                    "max": 20,
                    "type": "numeric"
                }
            ]
        )
        
        resp = self.client.get(f"/feedback/template/{template.pk}/rubric/")
        self.assertEqual(resp.status_code, 200)
        
        # Should show module info
        self.assertContains(resp, "CS301")
        self.assertContains(resp, "Software Engineering")
        
        # Should show categories
        self.assertContains(resp, "Design")
        self.assertContains(resp, "30 marks")
        self.assertContains(resp, "Testing")
        self.assertContains(resp, "Numeric scoring")
        
        # Should show grade bands
        self.assertContains(resp, "High 1st")
        self.assertContains(resp, "Low 1st")
        self.assertContains(resp, "Excellent design")
        
        # Should NOT show student fields
        self.assertNotContains(resp, "Student Name")
        self.assertNotContains(resp, "Mark Awarded")
    
    def test_template_feedback_sheet_view_shows_student_fields(self):
        """Feedback sheet view shows student fields and mark entry areas"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Software Engineering",
            module_code="CS301",
            assessment_title="CW1",
            max_marks=50,
            categories=[
                {"label": "Design", "max": 30, "type": "grade", "subdivision": "none"},
                {"label": "Testing", "max": 20, "type": "numeric"}
            ]
        )
        
        resp = self.client.get(f"/feedback/template/{template.pk}/feedback-sheet/")
        self.assertEqual(resp.status_code, 200)
        
        # Should show module info
        self.assertContains(resp, "CS301")
        self.assertContains(resp, "Software Engineering")
        
        # Should show student fields
        self.assertContains(resp, "Student Name")
        self.assertContains(resp, "Student ID")
        
        # Should show categories
        self.assertContains(resp, "Design")
        self.assertContains(resp, "Testing")
        
        # Should expose total_marks in the view context and show the numeric total
        self.assertIn('total_marks', resp.context)
        self.assertEqual(resp.context['total_marks'], 50)
        # Still assert the numeric total is present in the rendered HTML
        self.assertContains(resp, "50")

    def test_feedback_sheet_view_passes_overall_grade_in_context(self):
        """Feedback sheet view should calculate and pass overall_grade into context"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Software Engineering",
            module_code="CS301",
            assessment_title="CW1",
            weighting=40,
            max_marks=100,
            categories=[
                {"label": "Design", "max": 30},
                {"label": "Testing", "max": 70}
            ]
        )

        resp = self.client.get(f"/feedback/template/{template.pk}/feedback-sheet/")
        self.assertEqual(resp.status_code, 200)

        # Total category marks == max_marks, so percentage == 100% -> '1st'
        self.assertIn('overall_grade', resp.context)
        self.assertEqual(resp.context['overall_grade'], '1st')
    
    def test_rubric_url_pattern(self):
        """Rubric URL pattern resolves correctly"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test",
            module_code="CS101",
            assessment_title="Test",
            categories=[]
        )
        
        url = reverse('template_rubric', kwargs={'pk': template.pk})
        self.assertEqual(url, f"/feedback/template/{template.pk}/rubric/")
    
    def test_feedback_sheet_url_pattern(self):
        """Feedback sheet URL pattern resolves correctly"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test",
            module_code="CS101",
            assessment_title="Test",
            categories=[]
        )
        
        url = reverse('template_feedback_sheet', kwargs={'pk': template.pk})
        self.assertEqual(url, f"/feedback/template/{template.pk}/feedback-sheet/")


class ChartViewTests(TestCase):
    """Tests for chart configuration in template views"""
    
    def test_template_update_accepts_charts_field(self):
        """POST /feedback/template/<pk>/update/ can save charts"""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[
                {"label": "Design", "max": 30},
                {"label": "Implementation", "max": 70}
            ]
        )
        
        url = reverse("template_update", args=[template.pk])
        charts = [
            {
                "type": "radar",
                "title": "Performance Breakdown",
                "categories": ["Design", "Implementation"]
            }
        ]
        
        data = {
            "title": "Test Template",
            "module_code": "CS101",
            "module_title": "Intro to CS",
            "assessment_title": "Exam",
            "component": 1,
            "weighting": 50,
            "max_marks": 100,
            "categories": template.categories,
            "charts": charts
        }
        
        resp = self.client.post(url, json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        
        # Reload and verify
        template.refresh_from_db()
        self.assertEqual(len(template.charts), 1)
        self.assertEqual(template.charts[0]["type"], "radar")
        self.assertEqual(template.charts[0]["title"], "Performance Breakdown")
    
    def test_template_edit_includes_category_short_names(self):
        """The edit page should include saved category_short_names in the JS payload
        so the UI can pre-fill short-name inputs when editing an existing template."""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[
                {"label": "Design", "max": 30},
                {"label": "Implementation", "max": 70}
            ],
            charts=[
                {
                    "type": "radar",
                    "title": "Performance Breakdown",
                    "categories": ["Design", "Implementation"],
                    "category_short_names": {"Design": "Dsg", "Implementation": "Impl"}
                }
            ]
        )

        url = reverse('template_edit', args=[template.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # The template renders a JS payload `window.templateData` that should include
        # the saved charts JSON including the `category_short_names` key.
        content = resp.content.decode('utf-8')
        self.assertIn('category_short_names', content)
        self.assertIn('Dsg', content)
    def test_feedback_sheet_view_passes_charts_to_template(self):
        """Feedback sheet view includes charts in context"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[{"label": "Section 1", "max": 100}],
            charts=[
                {
                    "type": "histogram",
                    "title": "Class Distribution",
                    "data_source": "overall"
                }
            ]
        )
        
        resp = self.client.get(f"/feedback/template/{template.pk}/feedback-sheet/")
        self.assertEqual(resp.status_code, 200)
        
        # Check charts are in context
        self.assertIn("charts", resp.context)
        self.assertEqual(len(resp.context["charts"]), 1)
        self.assertEqual(resp.context["charts"][0]["type"], "histogram")
    
    def test_feedback_sheet_with_empty_charts(self):
        """Feedback sheet works with no charts configured"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[{"label": "Section 1", "max": 100}],
            charts=[]
        )
        
        resp = self.client.get(f"/feedback/template/{template.pk}/feedback-sheet/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["charts"]), 0)
    
    def test_radar_chart_can_store_category_short_names(self):
        """Radar charts can store optional short names for categories"""
        import json
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[
                {"label": "Implementation and Code Quality", "max": 40},
                {"label": "Documentation and Comments", "max": 30},
                {"label": "Testing", "max": 30}
            ]
        )
        
        url = reverse("template_update", args=[template.pk])
        charts = [
            {
                "type": "radar",
                "title": "Performance Overview",
                "categories": ["Implementation and Code Quality", "Documentation and Comments"],
                "category_short_names": {
                    "Implementation and Code Quality": "Code",
                    "Documentation and Comments": "Docs"
                }
            }
        ]
        
        data = {
            "title": "Test Template",
            "module_code": "CS101",
            "module_title": "Intro to CS",
            "assessment_title": "Exam",
            "component": 1,
            "weighting": 50,
            "max_marks": 100,
            "categories": template.categories,
            "charts": charts
        }
        
        resp = self.client.post(url, json.dumps(data), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        
        # Reload and verify short names are stored
        template.refresh_from_db()
        self.assertEqual(len(template.charts), 1)
        self.assertIn("category_short_names", template.charts[0])
        self.assertEqual(template.charts[0]["category_short_names"]["Implementation and Code Quality"], "Code")
        self.assertEqual(template.charts[0]["category_short_names"]["Documentation and Comments"], "Docs")
    
    def test_feedback_sheet_view_passes_short_names_in_charts(self):
        """Feedback sheet view includes category_short_names in chart data"""
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="CS101",
            module_title="Intro to CS",
            assessment_title="Exam",
            weighting=50,
            max_marks=100,
            categories=[
                {"label": "Very Long Category Name", "max": 50},
                {"label": "Another Long Name", "max": 50}
            ],
            charts=[
                {
                    "type": "radar",
                    "title": "Overview",
                    "categories": ["Very Long Category Name", "Another Long Name"],
                    "category_short_names": {
                        "Very Long Category Name": "Short1",
                        "Another Long Name": "Short2"
                    }
                }
            ]
        )
        
        resp = self.client.get(f"/feedback/template/{template.pk}/feedback-sheet/")
        self.assertEqual(resp.status_code, 200)
        
        # Check short names are in context
        self.assertIn("charts", resp.context)
        self.assertEqual(len(resp.context["charts"]), 1)
        self.assertIn("category_short_names", resp.context["charts"][0])
        self.assertEqual(resp.context["charts"][0]["category_short_names"]["Very Long Category Name"], "Short1")
