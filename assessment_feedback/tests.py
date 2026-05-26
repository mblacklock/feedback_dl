import os
import zipfile
import io
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile


class AssessmentFeedbackViewsTest(TestCase):
    def setUp(self):
        # Sample uploaded data representing spreadsheet rows
        self.sample_uploaded_data = [
            {"Student Name": "Alice Smith", "Student ID": "10001", "Design /30": 24, "Design Comments": "Good design", "Implementation /40": 35, "Implementation Comments": "Clean code", "Testing /30": 25, "Testing Comments": "Good coverage"},
            {"Student Name": "Bob Jones", "Student ID": "10002", "Design /30": 18, "Design Comments": "Lacks clean abstraction", "Implementation /40": 28, "Implementation Comments": "Some duplication", "Testing /30": 15, "Testing Comments": "Some gaps"}
        ]
        self.sample_headers = [
            "Student Name", "Student ID", "Design /30", "Design Comments", "Implementation /40", "Implementation Comments", "Testing /30", "Testing Comments"
        ]
        self.sample_mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {"column": "Design /30", "max_marks": 30, "weight": None, "comments_column": "Design Comments", "type": "numeric"},
                {"column": "Implementation /40", "max_marks": 40, "weight": None, "comments_column": "Implementation Comments", "type": "numeric"},
                {"column": "Testing /30", "max_marks": 30, "weight": None, "comments_column": "Testing Comments", "type": "numeric"}
            ]
        }

    def test_upload_file_get_returns_200(self):
        """GET /assessment-feedback/ returns 200 and renders the upload template"""
        url = reverse("upload_file")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cohort PDF Feedback Generator")

    def test_upload_file_post_redirects_to_confirm(self):
        """POST /assessment-feedback/ with valid Excel redirects to confirm page"""
        url = reverse("upload_file")
        
        # Load the dummy grades fixture Excel file
        fixture_path = os.path.join(
            r"c:\Backup Drive\Documents\django-apps\feedback_dl",
            "functional_tests", "fixtures", "dummy_grades.xlsx"
        )
        with open(fixture_path, "rb") as f:
            excel_data = f.read()
            
        uploaded_file = SimpleUploadedFile("dummy_grades.xlsx", excel_data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        resp = self.client.post(url, {"file": uploaded_file})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("/assessment-feedback/confirm/"))
        
        # Verify session state was correctly updated
        self.assertIn("headers", self.client.session)
        self.assertIn("uploaded_data", self.client.session)
        self.assertIn("mappings", self.client.session)

    def test_upload_infers_all_three_categories_from_fixture(self):
        """Uploading dummy_grades.xlsx must infer exactly Design, Implementation,
        and Testing as grading categories — with correct max_marks and comments columns."""
        fixture_path = os.path.join(
            r"c:\Backup Drive\Documents\django-apps\feedback_dl",
            "functional_tests", "fixtures", "dummy_grades.xlsx"
        )
        with open(fixture_path, "rb") as f:
            excel_data = f.read()

        uploaded_file = SimpleUploadedFile(
            "dummy_grades.xlsx", excel_data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp = self.client.post(reverse("upload_file"), {"file": uploaded_file})
        self.assertEqual(resp.status_code, 302)

        mappings = self.client.session["mappings"]

        # Name and ID must be inferred correctly
        self.assertEqual(mappings["col_student_name"], "Student Name")
        self.assertEqual(mappings["col_student_id"], "Student ID")

        categories = mappings["categories"]
        category_columns = [c["column"] for c in categories]

        # All three mark columns must be found
        self.assertIn("Design /30", category_columns,
                      msg=f"Expected 'Design /30' in categories, got: {category_columns}")
        self.assertIn("Implementation /40", category_columns,
                      msg=f"Expected 'Implementation /40' in categories, got: {category_columns}")
        self.assertIn("Testing /30", category_columns,
                      msg=f"Expected 'Testing /30' in categories, got: {category_columns}")

        # Comment columns must NOT appear as categories
        self.assertNotIn("Design Comments", category_columns)
        self.assertNotIn("Implementation Comments", category_columns)
        self.assertNotIn("Testing Comments", category_columns)

        # Max marks must be correctly parsed from column headers
        by_col = {c["column"]: c for c in categories}
        self.assertEqual(by_col["Design /30"]["max_marks"], 30)
        self.assertEqual(by_col["Implementation /40"]["max_marks"], 40)
        self.assertEqual(by_col["Testing /30"]["max_marks"], 30)

        # Comments columns must be correctly mapped
        self.assertEqual(by_col["Design /30"]["comments_column"], "Design Comments")
        self.assertEqual(by_col["Implementation /40"]["comments_column"], "Implementation Comments")
        self.assertEqual(by_col["Testing /30"]["comments_column"], "Testing Comments")

    def test_confirm_mappings_get_renders_mappings(self):
        """GET /assessment-feedback/confirm/ renders confirmation mapping layout"""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        url = reverse("confirm_mappings")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Confirm Data Mapping")
        self.assertContains(resp, "col_student_name")
        self.assertContains(resp, "Design /30")

    def test_confirm_mappings_post_saves_to_session_and_redirects(self):
        """POST /assessment-feedback/confirm/ saves mapped fields and redirects to process"""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        url = reverse("confirm_mappings")
        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            # Category mappings configuration
            "max_0": "30", "weight_0": "", "comments_0": "Design Comments", "type_0": "numeric",
            "max_1": "40", "weight_1": "", "comments_1": "Implementation Comments", "type_1": "numeric",
            "max_2": "30", "weight_2": "", "comments_2": "Testing Comments", "type_2": "numeric"
        }
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("/assessment-feedback/layout/"))

        # Verify mappings updated inside session
        updated_mappings = self.client.session["mappings"]
        self.assertEqual(updated_mappings["col_student_name"], "Student Name")
        self.assertEqual(updated_mappings["categories"][0]["max_marks"], 30)

    def test_process_feedback_generates_valid_zip(self):
        """GET /assessment-feedback/process/ processes data and returns a downloadable ZIP of PDFs"""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        url = reverse("process_feedback")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        self.assertTrue(resp.has_header("Content-Disposition"))
        self.assertIn("attachment; filename=student_feedback_reports.zip", resp["Content-Disposition"])

        # Inspect zip content
        zip_bytes = io.BytesIO(resp.content)
        with zipfile.ZipFile(zip_bytes, "r") as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 2)
            self.assertIn("10001_alice-smith.pdf", namelist)
            self.assertIn("10002_bob-jones.pdf", namelist)
            
            # Read first PDF header bytes (PDF header is %PDF-)
            pdf_data = zf.read("10001_alice-smith.pdf")
            self.assertEqual(pdf_data[:5], b"%PDF-")

    # -------------------------------------------------------------------------
    # Layout Builder tests
    # -------------------------------------------------------------------------

    def _set_full_session(self):
        """Helper: populate session with headers, data, and mappings."""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

    def test_configure_layout_get_returns_200_with_defaults(self):
        """GET /assessment-feedback/layout/ renders builder with default four blocks."""
        self._set_full_session()

        url = reverse("configure_layout")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # All four default blocks should appear in the response
        for label in ["Category Marks", "Feedback Comments", "Radar Chart", "Histogram Chart"]:
            self.assertContains(resp, label)

    def test_configure_layout_get_redirects_without_session(self):
        """GET /assessment-feedback/layout/ redirects to upload when session is empty."""
        url = reverse("configure_layout")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("upload_file"))

    def test_configure_layout_post_saves_order_and_width_to_session(self):
        """POST /assessment-feedback/layout/ persists custom block order and widths in session."""
        self._set_full_session()

        url = reverse("configure_layout")
        form_data = {
            # Reversed order: histogram first, then radar, feedback, category_marks
            "block_order": "histogram,radar_chart,feedback,category_marks",
            "enabled_histogram": "true",
            "width_histogram": "full",
            "enabled_radar_chart": "true",
            "width_radar_chart": "half",
            "enabled_feedback": "true",
            "width_feedback": "full",
            "enabled_category_marks": "true",
            "width_category_marks": "half",
        }
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("process_feedback"))

        saved_layout = self.client.session["layout"]
        self.assertEqual(len(saved_layout), 4)

        # First block should now be histogram
        self.assertEqual(saved_layout[0]["id"], "histogram")
        self.assertEqual(saved_layout[0]["width"], "full")
        self.assertTrue(saved_layout[0]["enabled"])

        # Second block should be radar_chart with half width
        self.assertEqual(saved_layout[1]["id"], "radar_chart")
        self.assertEqual(saved_layout[1]["width"], "half")

        # Last block should be category_marks
        self.assertEqual(saved_layout[3]["id"], "category_marks")
        self.assertEqual(saved_layout[3]["width"], "half")

    def test_configure_layout_post_disabled_block_not_enabled(self):
        """POST /assessment-feedback/layout/ correctly marks a block as disabled."""
        self._set_full_session()

        url = reverse("configure_layout")
        form_data = {
            "block_order": "category_marks,feedback,radar_chart,histogram",
            # radar_chart explicitly disabled (no enabled_radar_chart key → defaults to false)
            "enabled_category_marks": "true",
            "width_category_marks": "full",
            "enabled_feedback": "true",
            "width_feedback": "full",
            # enabled_radar_chart intentionally omitted → treated as "false"
            "width_radar_chart": "half",
            "enabled_histogram": "true",
            "width_histogram": "half",
        }
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)

        saved_layout = self.client.session["layout"]
        radar = next(b for b in saved_layout if b["id"] == "radar_chart")
        self.assertFalse(radar["enabled"])

    def test_process_feedback_respects_layout_exclusions(self):
        """Disabled layout blocks are omitted from the generated PDF context.

        We patch render_to_string to capture the context passed to the PDF
        template and assert that disabled blocks are absent.
        """
        from unittest.mock import patch

        self._set_full_session()

        # Disable radar_chart and histogram; keep category_marks and feedback
        custom_layout = [
            {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
            {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True},
            {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": False},
            {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": False},
        ]
        session = self.client.session
        session["layout"] = custom_layout
        session.save()

        # Capture the context passed to the PDF template
        captured_layouts = []

        original_render = __import__(
            "django.template.loader", fromlist=["render_to_string"]
        ).render_to_string

        def mock_render_to_string(template_name, context=None, request=None):
            if template_name == "assessment_feedback/feedback_pdf.html":
                captured_layouts.append(context.get("layout", []))
            return original_render(template_name, context, request=request)

        url = reverse("process_feedback")
        with patch(
            "assessment_feedback.views.render_to_string",
            side_effect=mock_render_to_string,
        ):
            # We still expect a real ZIP response
            resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)

        # At least one student layout was captured
        self.assertGreater(len(captured_layouts), 0)

        for layout in captured_layouts:
            ids = [b["id"] for b in layout]
            # Enabled blocks are present
            self.assertIn("category_marks", ids)
            self.assertIn("feedback", ids)
            # Disabled blocks are present in layout list but flagged disabled
            radar_blocks = [b for b in layout if b["id"] == "radar_chart"]
            self.assertTrue(all(not b["enabled"] for b in radar_blocks))
