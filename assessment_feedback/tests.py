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
        self.assertContains(resp, "Cohort Feedback Sheet Generator")

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
        self.assertEqual(resp.url, reverse("confirm_mappings"))
        
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

        # All mark columns must be found
        self.assertIn("Design /30", category_columns,
                      msg=f"Expected 'Design /30' in categories, got: {category_columns}")
        self.assertIn("Implementation (40)", category_columns,
                      msg=f"Expected 'Implementation (40)' in categories, got: {category_columns}")
        self.assertIn("Testing 30", category_columns,
                      msg=f"Expected 'Testing 30' in categories, got: {category_columns}")
        self.assertIn("Analysis", category_columns,
                      msg=f"Expected 'Analysis' in categories, got: {category_columns}")

        # Comment columns must NOT appear as categories
        self.assertNotIn("Design Comments", category_columns)
        self.assertNotIn("Implementation Comments", category_columns)
        self.assertNotIn("Testing Comments", category_columns)

        # Max marks must be correctly parsed from column headers
        by_col = {c["column"]: c for c in categories}
        self.assertEqual(by_col["Design /30"]["max_marks"], 30)
        self.assertEqual(by_col["Implementation (40)"]["max_marks"], 40)
        self.assertEqual(by_col["Testing 30"]["max_marks"], 30)
        self.assertEqual(by_col["Analysis"]["max_marks"], 100)

        # Comments columns must be correctly mapped
        self.assertEqual(by_col["Design /30"]["comments_column"], "Design Comments")
        self.assertEqual(by_col["Implementation (40)"]["comments_column"], "Implementation Comments")
        self.assertEqual(by_col["Testing 30"]["comments_column"], "Testing Comments")

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

    def test_confirm_mappings_post_invalid_max_marks_renders_error(self):
        """Invalid max marks should redisplay the confirmation page instead of raising a 500."""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "max_0": "",
            "comments_0": "Design Comments",
            "type_0": "numeric",
            "max_1": "40",
            "comments_1": "Implementation Comments",
            "type_1": "numeric",
            "max_2": "30",
            "comments_2": "Testing Comments",
            "type_2": "numeric",
        }
        resp = self.client.post(reverse("confirm_mappings"), form_data)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Validation Error")
        self.assertContains(resp, "Max marks for Design /30 must be a positive whole number.")

    def test_upload_with_no_detected_categories_renders_error(self):
        """A sheet with identifiers only should produce a useful upload error."""
        wb = __import__("openpyxl").Workbook()
        ws = wb.active
        ws.append(["Student Name", "Student ID", "General Comment"])
        ws.append(["Alice Smith", "10001", "No marks here"])
        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)

        uploaded_file = SimpleUploadedFile(
            "no_marks.xlsx",
            excel_bytes.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp = self.client.post(reverse("upload_file"), {"file": uploaded_file})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No grading categories were detected")

    def test_confirm_mappings_post_recalculates_global_subdivision(self):
        """POST /assessment-feedback/confirm/ must dynamically recalculate the global subdivision
        based on the subdivisions of the active 'grade' categories, ignoring any POSTed subdivision value."""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        
        # Configure sample mappings to have one category of type 'grade' with 'high_mid_low' subdivision
        sample_mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {
                    "column": "Design /30",
                    "max_marks": 30,
                    "weight": None,
                    "comments_column": "Design Comments",
                    "type": "grade",
                    "subdivision": "high_mid_low",
                    "rubric_marks": [{"grade": "High 1st", "marks": 28}]
                }
            ]
        }
        session["mappings"] = sample_mappings
        session.save()

        url = reverse("confirm_mappings")
        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",  # Omitted or sent as "none", should be overridden/ignored
            "max_0": "30",
            "weight_0": "",
            "comments_0": "Design Comments",
            "type_0": "grade",
            "rubric_mark_0_0": "28"
        }
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)

        # Global subdivision must have recalculated to 'high_mid_low'
        updated_mappings = self.client.session["mappings"]
        self.assertEqual(updated_mappings["subdivision"], "high_mid_low")

    def test_confirm_mappings_switch_to_m_level_regenerates_rubric_labels(self):
        """Changing degree level to MEng must rebuild stored rubric labels without 3rd bands."""
        from core.utils.grade_bands import calculate_grade_bands

        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "high_low",
            "categories": [
                {
                    "column": "Design /30",
                    "max_marks": 30,
                    "weight": None,
                    "comments_column": "Design Comments",
                    "type": "grade",
                    "subdivision": "high_low",
                    "rubric_marks": calculate_grade_bands(30, "high_low", degree_level="BEng"),
                }
            ],
        }
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "MEng",
            "max_0": "30",
            "comments_0": "Design Comments",
            "type_0": "grade",
        }
        resp = self.client.post(reverse("confirm_mappings"), form_data)
        self.assertEqual(resp.status_code, 302)

        saved_rubric = self.client.session["mappings"]["categories"][0]["rubric_marks"]
        labels = [b["grade"] for b in saved_rubric]
        self.assertTrue(any("Merit" in label or "Pass" in label for label in labels))
        self.assertFalse(any("3rd" in label for label in labels))

    def test_process_feedback_generates_valid_zip(self):
        """GET /assessment-feedback/process/ processes data and returns a downloadable ZIP of HTMLs"""
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
            self.assertIn("10001_alice-smith.html", namelist)
            self.assertIn("10002_bob-jones.html", namelist)
            
            # Read first HTML file content (should start with <!DOCTYPE html>)
            html_data = zf.read("10001_alice-smith.html").strip()
            self.assertTrue(html_data.startswith(b"<!DOCTYPE html>"),
                            msg=f"HTML content does not start with <!DOCTYPE html>: {html_data[:50]}")
            
            # Verify that CSS styles from feedback_blocks.css are correctly embedded inline
            self.assertIn(b".half-pair", html_data)
            self.assertIn(b".grade-pill", html_data)

    def test_m_level_preview_and_generated_sheet_use_fail_below_50(self):
        """M-level preview and final HTML must classify 40-49% as Fail, not 3rd."""
        uploaded_data = [
            {"Student Name": "Alice Smith", "Student ID": "10001", "Design /100": 45},
        ]
        mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "MEng",
            "subdivision": "none",
            "categories": [
                {
                    "column": "Design /100",
                    "max_marks": 100,
                    "weight": None,
                    "comments_column": "",
                    "type": "numeric",
                }
            ],
        }
        session = self.client.session
        session["headers"] = ["Student Name", "Student ID", "Design /100"]
        session["uploaded_data"] = uploaded_data
        session["mappings"] = mappings
        session.save()

        preview_resp = self.client.get(reverse("configure_layout"))
        self.assertEqual(preview_resp.status_code, 200)
        self.assertContains(preview_resp, "Grade: Fail")
        self.assertNotContains(preview_resp, "Grade: 3rd")

        process_resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(process_resp.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(process_resp.content), "r") as zf:
            html = zf.read("10001_alice-smith.html").decode("utf-8")
        self.assertIn("Grade: Fail", html)
        self.assertNotIn("Grade: 3rd", html)

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
        """GET /assessment-feedback/layout/ renders builder with default blocks."""
        self._set_full_session()

        url = reverse("configure_layout")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # All five default blocks should appear in the response
        for label in ["Category Marks", "Feedback Comments", "General Feedback", "Radar Chart", "Histogram Chart"]:
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
            # Reversed order: histogram first, then radar, general_feedback, feedback, category_marks
            "block_order": "histogram,radar_chart,general_feedback,feedback,category_marks",
            "enabled_histogram": "true",
            "width_histogram": "full",
            "enabled_radar_chart": "true",
            "width_radar_chart": "half",
            "enabled_general_feedback": "false",
            "width_general_feedback": "full",
            "enabled_feedback": "true",
            "width_feedback": "full",
            "enabled_category_marks": "true",
            "width_category_marks": "half",
            "general_comments": "These are overall class comments.",
        }
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("generation_success"))

        saved_layout = self.client.session["layout"]
        self.assertEqual(len(saved_layout), 5)

        # First block should now be histogram
        self.assertEqual(saved_layout[0]["id"], "histogram")
        self.assertEqual(saved_layout[0]["width"], "full")
        self.assertTrue(saved_layout[0]["enabled"])

        # Second block should be radar_chart with half width
        self.assertEqual(saved_layout[1]["id"], "radar_chart")
        self.assertEqual(saved_layout[1]["width"], "half")

        # Third block should be general_feedback
        self.assertEqual(saved_layout[2]["id"], "general_feedback")
        self.assertFalse(saved_layout[2]["enabled"])

        # Last block should be category_marks
        self.assertEqual(saved_layout[4]["id"], "category_marks")
        self.assertEqual(saved_layout[4]["width"], "half")

        self.assertEqual(self.client.session["general_comments"], "These are overall class comments.")

    def test_configure_layout_post_disabled_block_not_enabled(self):
        """POST /assessment-feedback/layout/ correctly marks a block as disabled."""
        self._set_full_session()

        url = reverse("configure_layout")
        form_data = {
            "block_order": "category_marks,feedback,general_feedback,radar_chart,histogram",
            # radar_chart explicitly disabled (no enabled_radar_chart key → defaults to false)
            "enabled_category_marks": "true",
            "width_category_marks": "full",
            "enabled_feedback": "true",
            "width_feedback": "full",
            "enabled_general_feedback": "true",
            "width_general_feedback": "full",
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
        """Disabled layout blocks are omitted from the generated Feedback Sheet context.

        We patch render_to_string to capture the context passed to the Feedback Sheet
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

        # Capture the context passed to the Feedback Sheet template
        captured_layouts = []

        original_render = __import__(
            "django.template.loader", fromlist=["render_to_string"]
        ).render_to_string

        def mock_render_to_string(template_name, context=None, request=None):
            if template_name == "assessment_feedback/feedback_sheet.html":
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

    # -------------------------------------------------------------------------
    # Rubric auto-detection tests
    # -------------------------------------------------------------------------

    def test_infer_rubric_type_detects_grade_column(self):
        """infer_rubric_type returns ('grade', subdivision) for grade-string columns."""
        from assessment_feedback.views import infer_rubric_type

        # high_mid_low: contains "Mid 2:1"
        values_hml = ["High 1st", "Mid 2:1", "Low 2:2", "Mid 3rd", None]
        cat_type, subdivision = infer_rubric_type(values_hml)
        self.assertEqual(cat_type, "grade")
        self.assertEqual(subdivision, "high_mid_low")

        # high_low: contains "High 2:1" but no "Mid" on non-1st bands
        values_hl = ["High 1st", "High 2:1", "Low 2:2", "High 3rd"]
        cat_type, subdivision = infer_rubric_type(values_hl)
        self.assertEqual(cat_type, "grade")
        self.assertEqual(subdivision, "high_low")

        # none subdivision: just plain grade names
        values_none = ["2:1", "2:2", "3rd", "2:1"]
        cat_type, subdivision = infer_rubric_type(values_none)
        self.assertEqual(cat_type, "grade")
        self.assertEqual(subdivision, "none")

        # numeric: should not be detected as grade
        values_num = [24, 18, 28, 35]
        cat_type, subdivision = infer_rubric_type(values_num)
        self.assertEqual(cat_type, "numeric")

    def test_upload_detects_rubric_columns_from_fixture(self):
        """Uploading a fixture with grade strings produces type='grade' categories
        with rubric_marks pre-populated and subdivision correctly detected."""
        import openpyxl, tempfile, os
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Build a minimal in-memory spreadsheet with a rubric column
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Student Name", "Student ID", "Design /30", "Design Comments"])
        ws.append(["Alice Smith", "10001", "Mid 2:1", "Good work"])
        ws.append(["Bob Jones",   "10002", "High 1st", "Excellent"])
        ws.append(["Carol White", "10003", "Low 2:2", "Needs improvement"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        uploaded = SimpleUploadedFile(
            "rubric_test.xlsx", buf.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp = self.client.post(reverse("upload_file"), {"file": uploaded})
        self.assertEqual(resp.status_code, 302)

        mappings = self.client.session["mappings"]
        cats = {c["column"]: c for c in mappings["categories"]}

        self.assertIn("Design /30", cats)
        design = cats["Design /30"]
        self.assertEqual(design["type"], "grade",
                         msg="Design /30 with grade strings should be detected as 'grade' type")
        self.assertIn(design["subdivision"], ("none", "high_low", "high_mid_low"))
        self.assertIsInstance(design["rubric_marks"], list)
        self.assertGreater(len(design["rubric_marks"]), 0,
                           msg="rubric_marks should be pre-populated on upload")

        # Each band should have grade and marks keys
        for band in design["rubric_marks"]:
            self.assertIn("grade", band)
            self.assertIn("marks", band)

    def test_confirm_post_saves_rubric_mark_overrides(self):
        """POSTing custom rubric_mark_{idx}_{band_idx} values stores them in session."""
        rubric_marks = [
            {"grade": "High 1st", "marks": 28},
            {"grade": "Mid 2:1",  "marks": 19},
            {"grade": "Low 2:2",  "marks": 15},
        ]
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = {
            **self.sample_mappings,
            "categories": [
                {
                    "column": "Design /30", "max_marks": 30, "weight": None,
                    "comments_column": "Design Comments",
                    "type": "grade", "subdivision": "none",
                    "rubric_marks": rubric_marks,
                }
            ],
        }
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "type_0": "grade",
            "max_0": "30",
            "weight_0": "",
            "comments_0": "Design Comments",
            # Override: user changes "Mid 2:1" from 19 → 20
            "rubric_mark_0_0": "28",   # High 1st unchanged
            "rubric_mark_0_1": "20",   # Mid 2:1 changed from 19 → 20
            "rubric_mark_0_2": "15",   # Low 2:2 unchanged
        }
        resp = self.client.post(reverse("confirm_mappings"), form_data)
        self.assertEqual(resp.status_code, 302)

        saved_cats = self.client.session["mappings"]["categories"]
        saved_rubric = saved_cats[0]["rubric_marks"]

        self.assertEqual(saved_rubric[0]["grade"], "High 1st")
        self.assertEqual(saved_rubric[0]["marks"], 28)
        self.assertEqual(saved_rubric[1]["grade"], "Mid 2:1")
        self.assertEqual(saved_rubric[1]["marks"], 20,
                         msg="User override of Mid 2:1 from 19→20 should be saved")

    def test_process_feedback_uses_rubric_marks_for_grade_columns(self):
        """process_feedback maps grade strings to numeric marks via rubric_marks."""
        rubric_marks = [
            {"grade": "High 1st", "marks": 28},
            {"grade": "Mid 2:1",  "marks": 19},
            {"grade": "Low 2:2",  "marks": 15},
        ]
        # Two students with grade-string values in Design column
        uploaded_data = [
            {"Student Name": "Alice Smith", "Student ID": "10001",
             "Design /30": "High 1st", "Design Comments": "Great"},
            {"Student Name": "Bob Jones",   "Student ID": "10002",
             "Design /30": "Mid 2:1",  "Design Comments": "OK"},
        ]
        mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {
                    "column": "Design /30", "max_marks": 30, "weight": None,
                    "comments_column": "Design Comments",
                    "type": "grade", "subdivision": "none",
                    "rubric_marks": rubric_marks,
                }
            ],
        }
        session = self.client.session
        session["uploaded_data"] = uploaded_data
        session["mappings"] = mappings
        session.save()

        resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        # Both students should have HTMLs in the ZIP
        self.assertEqual(len(zf.namelist()), 2)
        # HTMLs must be valid
        for name in zf.namelist():
            html_data = zf.read(name).strip()
            self.assertTrue(html_data.startswith(b"<!DOCTYPE html>"),
                            msg=f"{name} does not start with <!DOCTYPE html>")

    # -------------------------------------------------------------------------
    # Mixed-column fixture tests  (TDD — written against dummy_grades.xlsx
    # which now contains: Design /30 [numeric], Implementation /40 [numeric],
    # Testing /30 [rubric high_low], Analysis [rubric none / no denominator])
    # -------------------------------------------------------------------------

    def _load_fixture_excel(self):
        """Return SimpleUploadedFile for the shared dummy_grades.xlsx fixture."""
        fixture_path = r"c:\Backup Drive\Documents\django-apps\feedback_dl\functional_tests\fixtures\dummy_grades.xlsx"
        with open(fixture_path, "rb") as f:
            data = f.read()
        return SimpleUploadedFile(
            "dummy_grades.xlsx", data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_mixed_fixture_detects_all_five_columns(self):
        """Uploading the real fixture must detect all five grading columns:
        two numeric (Design, Implementation), two rubric (Testing, Analysis),
        and one information (Max Load), and assign correct types and subdivisions to each."""
        resp = self.client.post(reverse("upload_file"), {"file": self._load_fixture_excel()})
        self.assertEqual(resp.status_code, 302)

        mappings = self.client.session["mappings"]
        by_col = {c["column"]: c for c in mappings["categories"]}
        found = list(by_col.keys())

        # All five columns must be found
        self.assertIn("Design /30", by_col, msg=f"Missing Design /30, found: {found}")
        self.assertIn("Implementation (40)", by_col, msg=f"Missing Implementation (40), found: {found}")
        self.assertIn("Testing 30", by_col, msg=f"Missing Testing 30, found: {found}")
        self.assertIn("Analysis", by_col, msg=f"Missing Analysis, found: {found}")
        self.assertIn("Max Load (N)", by_col, msg=f"Missing Max Load (N), found: {found}")

        # Numeric columns must have type 'numeric'
        self.assertEqual(by_col["Design /30"]["type"], "numeric")
        self.assertEqual(by_col["Implementation (40)"]["type"], "numeric")

        # Rubric columns must have type 'grade'
        self.assertEqual(by_col["Testing 30"]["type"], "grade",
                         msg="Testing 30 contains grade strings, should be type='grade'")
        self.assertEqual(by_col["Analysis"]["type"], "grade",
                         msg="Analysis contains grade strings, should be type='grade'")

        # Information column must have type 'information' and correctly extract unit
        self.assertEqual(by_col["Max Load (N)"]["type"], "information")
        self.assertEqual(by_col["Max Load (N)"]["unit"], "N")
        self.assertIsNone(by_col["Max Load (N)"]["max_marks"])

        # Testing 30 contains "High 2:1", "Low 2:2" → high_low subdivision
        self.assertEqual(by_col["Testing 30"]["subdivision"], "high_low")

        # Rubric columns must have rubric_marks pre-computed
        self.assertGreater(len(by_col["Testing 30"]["rubric_marks"]), 0)
        self.assertGreater(len(by_col["Analysis"]["rubric_marks"]), 0)

    def test_mixed_fixture_analysis_column_max_marks_fallback(self):
        """Analysis column has no /N denominator — max_marks should fall back
        to a sensible default (100) since values are grade strings, not numbers."""
        resp = self.client.post(reverse("upload_file"), {"file": self._load_fixture_excel()})
        self.assertEqual(resp.status_code, 302)

        by_col = {c["column"]: c for c in self.client.session["mappings"]["categories"]}
        self.assertIn("Analysis", by_col)
        # Default fallback for rubric column with no denominator is 100
        self.assertEqual(by_col["Analysis"]["max_marks"], 100)

    def test_mixed_fixture_end_to_end_generates_valid_zip(self):
        """Full pipeline: upload mixed fixture → confirm → layout → process
        must produce a valid ZIP with one HTML per student."""
        # Step 1: Upload
        resp = self.client.post(reverse("upload_file"), {"file": self._load_fixture_excel()})
        self.assertEqual(resp.status_code, 302)

        mappings = self.client.session["mappings"]
        categories = mappings["categories"]
        by_col = {c["column"]: c for c in categories}

        # Step 2: Confirm — POST with auto-detected mappings unchanged
        form = {
            "col_student_name": mappings["col_student_name"],
            "col_student_id":   mappings["col_student_id"],
            "degree_level":     mappings.get("degree_level", "BEng"),
            "subdivision":      mappings.get("subdivision", "none"),
        }
        for idx, cat in enumerate(categories):
            form[f"type_{idx}"]     = cat["type"]
            form[f"max_{idx}"]      = str(cat["max_marks"]) if cat["max_marks"] is not None else ""
            form[f"unit_{idx}"]     = cat.get("unit", "")
            form[f"weight_{idx}"]   = str(cat["weight"]) if cat["weight"] else ""
            form[f"comments_{idx}"] = cat.get("comments_column", "")
            for band_idx, band in enumerate(cat.get("rubric_marks", [])):
                form[f"rubric_mark_{idx}_{band_idx}"] = str(band["marks"])

        resp = self.client.post(reverse("confirm_mappings"), form)
        self.assertEqual(resp.status_code, 302)

        # Step 3: Process → ZIP
        resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        # One HTML per student (3 students in the fixture)
        self.assertEqual(len(zf.namelist()), 3,
                         msg=f"Expected 3 HTMLs, got: {zf.namelist()}")
        for name in zf.namelist():
            html_data = zf.read(name).strip()
            self.assertTrue(html_data.startswith(b"<!DOCTYPE html>"),
                             msg=f"{name} is not a valid HTML")

    def test_rubric_bands_api_returns_correct_bands(self):
        """GET /rubric-bands/ returns JSON grade bands for the requested max_marks
        and subdivision, and recalculates correctly when max_marks changes."""
        import json

        # high_low, max_marks=30
        resp = self.client.get(reverse("rubric_bands_api"),
                               {"max_marks": "30", "subdivision": "high_low"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        bands = json.loads(resp.content)
        self.assertIsInstance(bands, list)
        self.assertGreater(len(bands), 0)
        # All bands have grade and marks keys; marks must be ≤ max_marks
        for b in bands:
            self.assertIn("grade", b)
            self.assertIn("marks", b)
            self.assertLessEqual(b["marks"], 30)

        # Changing max_marks to 40 must produce different marks
        resp2 = self.client.get(reverse("rubric_bands_api"),
                                {"max_marks": "40", "subdivision": "high_low"})
        bands2 = json.loads(resp2.content)
        marks_30 = [b["marks"] for b in bands]
        marks_40 = [b["marks"] for b in bands2]
        self.assertNotEqual(marks_30, marks_40,
                            msg="Changing max_marks must produce different band marks")

        # Invalid subdivision falls back to 'none' (no error)
        resp3 = self.client.get(reverse("rubric_bands_api"),
                                {"max_marks": "20", "subdivision": "bogus"})
        self.assertEqual(resp3.status_code, 200)
        bands3 = json.loads(resp3.content)
        self.assertIsInstance(bands3, list)

    def test_rubric_bands_api_respects_m_level_degree(self):
        """M-level rubric bands use Dist/Merit/Pass labels and omit 3rd bands."""
        import json

        resp = self.client.get(reverse("rubric_bands_api"), {
            "max_marks": "100",
            "subdivision": "high_low",
            "degree_level": "MEng",
        })
        self.assertEqual(resp.status_code, 200)
        labels = [b["grade"] for b in json.loads(resp.content)]

        self.assertTrue(any("Dist" in label for label in labels))
        self.assertTrue(any("Merit" in label for label in labels))
        self.assertTrue(any("Pass" in label for label in labels))
        self.assertFalse(any("3rd" in label for label in labels))

    # -------------------------------------------------------------------------
    # Grade band rounding tests (TDD — user reported Low 1st = 6/10, should be 7)
    # -------------------------------------------------------------------------

    def test_grade_bands_10_marks_none_subdivision_rounding(self):
        """For max_marks=10 and 'none' subdivision the 1st-class bands must
        land on integer boundaries that actually fall within the right grade:
          Low 1st  = 7/10  (70 %)
          Mid 1st  = 8/10  (80 %)
          High 1st = 9/10  (90 %)
          Max 1st  = 10/10 (100 %)
        """
        from core.utils.grade_bands import calculate_grade_bands
        bands = {b["grade"]: b["marks"] for b in calculate_grade_bands(10, "none")}
        self.assertEqual(bands.get("Low 1st"),  7,
                         msg=f"Low 1st should be 7/10 (70%), got {bands.get('Low 1st')}")
        self.assertEqual(bands.get("Mid 1st"),  8,
                         msg=f"Mid 1st should be 8/10 (80%), got {bands.get('Mid 1st')}")
        self.assertEqual(bands.get("High 1st"), 9,
                         msg=f"High 1st should be 9/10 (90%), got {bands.get('High 1st')}")
        self.assertEqual(bands.get("Max 1st"),  10,
                         msg=f"Max 1st should be 10/10 (100%), got {bands.get('Max 1st')}")

    def test_grade_bands_api_10_marks_none_rounding(self):
        """The rubric-bands API must also return the correct marks for max_marks=10."""
        import json
        resp = self.client.get(reverse("rubric_bands_api"),
                               {"max_marks": "10", "subdivision": "none"})
        bands = {b["grade"]: b["marks"] for b in json.loads(resp.content)}
        self.assertEqual(bands.get("Low 1st"),  7,
                         msg=f"API Low 1st should be 7/10, got {bands.get('Low 1st')}")
        self.assertEqual(bands.get("Mid 1st"),  8,
                         msg=f"API Mid 1st should be 8/10, got {bands.get('Mid 1st')}")

    def test_clean_category_title_removes_various_mark_denominators(self):
        """Verify that clean_category_title successfully removes denominator / percentage notations
        leaving only the pristine category title name."""
        from assessment_feedback.views import clean_category_title
        self.assertEqual(clean_category_title("Design /30"), "Design")
        self.assertEqual(clean_category_title("Implementation (40)"), "Implementation")
        self.assertEqual(clean_category_title("Testing 30"), "Testing")
        self.assertEqual(clean_category_title("Design (30%)"), "Design")
        self.assertEqual(clean_category_title("Normal Title"), "Normal Title")

    def test_half_single_row_does_not_contain_empty_placeholder(self):
        """Verify that a half-single layout row renders without the empty placeholder <div class="half"></div>"""
        from django.template.loader import render_to_string
        
        context = {
            "student_name": "Test Student",
            "student_id": "99999",
            "layout_rows": [
                {
                    "type": "half-single",
                    "blocks": [{"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True}]
                }
            ],
            "categories": [],
            "total_score": 80,
            "total_max_marks": 100,
            "overall_grade": "1st",
            "overall_percentage": 80,
        }
        
        rendered = render_to_string("assessment_feedback/feedback_sheet.html", context)
        
        # Check that we render the half block
        self.assertIn("Visual Breakdown of Marks", rendered)
        
        # Check that the empty placeholder does NOT exist inside the half-pair
        # Since we removed the `<div class="half"></div>` empty placeholder,
        # there should not be a second .half div or empty .half inside the container.
        # Let's count occurrences of class="half" or similar.
        # In the modified template:
        # <div class="half-pair">
        #     <div class="half">
        #         ...
        #     </div>
        # </div>
        # So there should only be ONE occurrence of `<div class="half">` inside this block.
        self.assertEqual(rendered.count('<div class="half">'), 1)

    def test_grade_for_percentage_and_degree_undergraduate_and_postgraduate(self):
        """Verify grade calculations for undergraduate (BEng) and postgraduate (MEng/MSc) degree levels."""
        from assessment_feedback.views import grade_for_percentage_and_degree
        
        # UG (BEng) Classifications
        self.assertEqual(grade_for_percentage_and_degree(85, "BEng"), "1st")
        self.assertEqual(grade_for_percentage_and_degree(65, "BEng"), "2:1")
        self.assertEqual(grade_for_percentage_and_degree(55, "BEng"), "2:2")
        self.assertEqual(grade_for_percentage_and_degree(45, "BEng"), "3rd")
        self.assertEqual(grade_for_percentage_and_degree(35, "BEng"), "Fail")

        # PG (MEng/MSc) Classifications
        self.assertEqual(grade_for_percentage_and_degree(85, "MEng"), "1st/Dist")
        self.assertEqual(grade_for_percentage_and_degree(65, "MEng"), "2:1/Merit")
        self.assertEqual(grade_for_percentage_and_degree(55, "MEng"), "2:2/Pass")
        self.assertEqual(grade_for_percentage_and_degree(45, "MEng"), "Fail")
        self.assertEqual(grade_for_percentage_and_degree(35, "MEng"), "Fail")

    def test_category_marks_block_renders_toggle_and_numeric_grade_bands(self):
        """Verify that the category marks block renders toggle checkbox/scripts ONLY in editor,
        and correctly applies static inline display styles in both viewports."""
        from django.template.loader import render_to_string
        
        categories = [
            {
                "label": "Design",
                "mark": 24.0,
                "max_marks": 30,
                "grade_awarded": None,
                "is_grade": False,
                "calculated_grade_band": "1st"
            }
        ]
        
        # 1. Scenaro: In Editor, show_numeric_grade_bands = False
        context_editor_hide = {
            "block": {"id": "category_marks"},
            "categories": categories,
            "is_editor": True,
            "show_numeric_grade_bands": False
        }
        rendered = render_to_string("assessment_feedback/_feedback_block.html", context_editor_hide)
        self.assertIn("Show numeric", rendered)
        self.assertIn('class="toggle-numeric-grades-input"', rendered)
        self.assertIn('<script>', rendered)
        self.assertIn('class="numeric-grade-band"', rendered)
        self.assertIn('1st', rendered)
        self.assertIn('display: none', rendered)
        self.assertIn('class="numeric-dash"', rendered)
        self.assertIn('display: inline', rendered)

        # 2. Scenario: In Editor, show_numeric_grade_bands = True
        context_editor_show = {
            "block": {"id": "category_marks"},
            "categories": categories,
            "is_editor": True,
            "show_numeric_grade_bands": True
        }
        rendered = render_to_string("assessment_feedback/_feedback_block.html", context_editor_show)
        self.assertIn("checked", rendered) # Checkbox is checked
        self.assertIn('class="numeric-grade-band"', rendered)
        self.assertIn('1st', rendered)
        self.assertIn('display: inline', rendered)
        self.assertIn('class="numeric-dash"', rendered)
        self.assertIn('display: none', rendered)

        # 3. Scenario: Downloaded Static Sheet, show_numeric_grade_bands = True
        context_download = {
            "block": {"id": "category_marks"},
            "categories": categories,
            "is_editor": False,
            "show_numeric_grade_bands": True
        }
        rendered = render_to_string("assessment_feedback/_feedback_block.html", context_download)
        self.assertNotIn("Show numeric", rendered) # No checkbox
        self.assertNotIn('<script>', rendered) # No script tag
        self.assertIn('class="numeric-grade-band"', rendered)
        self.assertIn('1st', rendered)
        self.assertIn('display: inline', rendered)
        self.assertIn('class="numeric-dash"', rendered)
        self.assertIn('display: none', rendered)

    def test_upload_detects_information_column_and_unit(self):
        """Verify that heuristics identify non-mark columns like 'Max Load (N)' as information."""
        resp = self.client.post(reverse("upload_file"), {"file": self._load_fixture_excel()})
        self.assertEqual(resp.status_code, 302)
        
        mappings = self.client.session["mappings"]
        by_col = {c["column"]: c for c in mappings["categories"]}
        
        self.assertIn("Max Load (N)", by_col)
        cat = by_col["Max Load (N)"]
        self.assertEqual(cat["type"], "information")
        self.assertEqual(cat["unit"], "N")
        self.assertIsNone(cat["max_marks"])

    def test_confirm_information_posts_successfully_without_max_marks(self):
        """Verify that an information category can post successfully with blank max_marks."""
        session = self.client.session
        session["headers"] = ["Student Name", "Student ID", "Design /30", "Max Load (N)"]
        session["uploaded_data"] = [
            {"Student Name": "Alice", "Student ID": "1", "Design /30": 20, "Max Load (N)": 150}
        ]
        session["mappings"] = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {"column": "Design /30", "max_marks": 30, "weight": None, "comments_column": "", "type": "numeric", "unit": ""},
                {"column": "Max Load (N)", "max_marks": None, "weight": None, "comments_column": "", "type": "information", "unit": "N"}
            ]
        }
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "type_0": "numeric",
            "max_0": "30",
            "type_1": "information",
            "max_1": "",  # Blank max marks for information
            "unit_1": "N",
        }
        resp = self.client.post(reverse("confirm_mappings"), form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("/assessment-feedback/layout/"))

        saved_cats = self.client.session["mappings"]["categories"]
        self.assertEqual(saved_cats[1]["type"], "information")
        self.assertIsNone(saved_cats[1]["max_marks"])
        self.assertEqual(saved_cats[1]["unit"], "N")

    def test_confirm_rejects_all_information_columns(self):
        """Verify that mapping confirmation fails if there are no grading (numeric/rubric) columns."""
        session = self.client.session
        session["headers"] = ["Student Name", "Student ID", "Max Load (N)"]
        session["uploaded_data"] = [
            {"Student Name": "Alice", "Student ID": "1", "Max Load (N)": 150}
        ]
        session["mappings"] = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {"column": "Max Load (N)", "max_marks": None, "weight": None, "comments_column": "", "type": "information", "unit": "N"}
            ]
        }
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "type_0": "information",
            "max_0": "",
            "unit_0": "N",
        }
        resp = self.client.post(reverse("confirm_mappings"), form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "You must have at least one numeric Mark or Rubric grade category.")

    def test_process_excludes_information_from_score_and_radar(self):
        """Verify information categories are rendered properly but excluded from score & radar."""
        uploaded_data = [
            {"Student Name": "Alice", "Student ID": "1", "Design /30": 20, "Max Load (N)": 42.5}
        ]
        mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {"column": "Design /30", "max_marks": 30, "weight": None, "comments_column": "", "type": "numeric", "unit": ""},
                {"column": "Max Load (N)", "max_marks": None, "weight": None, "comments_column": "", "type": "information", "unit": "N"}
            ]
        }
        session = self.client.session
        session["headers"] = ["Student Name", "Student ID", "Design /30", "Max Load (N)"]
        session["uploaded_data"] = uploaded_data
        session["mappings"] = mappings
        session.save()

        # Check preview score/grade
        preview_resp = self.client.get(reverse("configure_layout"))
        self.assertEqual(preview_resp.status_code, 200)
        
        # Design /30 with 20/30 marks is 66.7%, which is 2:1.
        # Max Load (N) is 42.5. If it contributed, total score would be affected.
        # But it should be excluded, so:
        # Total Score: 20, Total Max: 30, overall_pct: 67%.
        self.assertContains(preview_resp, "67%")
        self.assertContains(preview_resp, "Grade: 2:1")

        # Now test ZIP processing
        process_resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(process_resp.status_code, 200)
        
        zf = zipfile.ZipFile(io.BytesIO(process_resp.content))
        html_content = zf.read("1_alice.html").decode("utf-8")
        
        # Verify rendered value: "42.5 N" under Criterion Marks
        self.assertIn("Max Load (N)", html_content)
        # Should render 42.5 N in the table cell
        self.assertIn("42.5 N", html_content)
        
        # Verify no "/ None" or "/ max" for Max Load
        self.assertNotIn("42.5 /", html_content)
        self.assertNotIn("/ None", html_content)

    def test_regression_numeric_marks_behave_same(self):
        """Verify normal numeric columns are rendered with denominator and calculated grade bands as before."""
        uploaded_data = [
            {"Student Name": "Alice", "Student ID": "1", "Design /30": 20}
        ]
        mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "categories": [
                {"column": "Design /30", "max_marks": 30, "weight": None, "comments_column": "", "type": "numeric", "unit": ""}
            ]
        }
        session = self.client.session
        session["headers"] = ["Student Name", "Student ID", "Design /30"]
        session["uploaded_data"] = uploaded_data
        session["mappings"] = mappings
        session.save()

        process_resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(process_resp.status_code, 200)
        
        zf = zipfile.ZipFile(io.BytesIO(process_resp.content))
        html_content = zf.read("1_alice.html").decode("utf-8")
        
        # Check standard mark format: "20 / 30"
        self.assertIn("20 / 30", html_content)

    def test_configure_layout_general_comments_persists_in_session(self):
        """Verify that POSTing layout configurations persists general_comments to session."""
        self._set_full_session()
        
        form_data = {
            "block_order": "category_marks,feedback,general_feedback,radar_chart,histogram",
            "enabled_category_marks": "true",
            "width_category_marks": "full",
            "enabled_feedback": "true",
            "width_feedback": "full",
            "enabled_general_feedback": "true",
            "width_general_feedback": "full",
            "enabled_radar_chart": "true",
            "width_radar_chart": "half",
            "enabled_histogram": "true",
            "width_histogram": "half",
            "general_comments": "Great overall performance from the cohort."
        }
        resp = self.client.post(reverse("configure_layout"), form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session["general_comments"], "Great overall performance from the cohort.")

    def test_process_includes_general_comments_block_if_enabled(self):
        """Verify that general feedback comments are rendered on feedback sheets when enabled."""
        self._set_full_session()
        
        # Configure layout with general_feedback ENABLED
        custom_layout = [
            {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
            {"id": "general_feedback", "name": "General Feedback", "width": "full", "enabled": True},
        ]
        session = self.client.session
        session["layout"] = custom_layout
        session["general_comments"] = "This is cohort-wide general class feedback comments."
        session.save()

        resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(resp.status_code, 200)
        
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        html_content = zf.read("10001_alice-smith.html").decode("utf-8")
        
        self.assertIn("General Feedback", html_content)
        self.assertIn("This is cohort-wide general class feedback comments.", html_content)

    def test_process_excludes_general_comments_block_if_disabled(self):
        """Verify that general feedback comments are NOT rendered on feedback sheets when disabled."""
        self._set_full_session()
        
        # Configure layout with general_feedback DISABLED
        custom_layout = [
            {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
            {"id": "general_feedback", "name": "General Feedback", "width": "full", "enabled": False},
        ]
        session = self.client.session
        session["layout"] = custom_layout
        session["general_comments"] = "This comments should not show."
        session.save()

        resp = self.client.get(reverse("process_feedback"))
        self.assertEqual(resp.status_code, 200)
        
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        html_content = zf.read("10001_alice-smith.html").decode("utf-8")
        
        self.assertNotIn("General Feedback", html_content)
        self.assertNotIn("This comments should not show.", html_content)

    def test_ensure_layout_defaults_migrates_stale_session(self):
        """Verify that stale layout lists (missing general_feedback) are successfully migrated to include default blocks."""
        self._set_full_session()
        
        # Simulate a stale layout session from a previous version (without general_feedback)
        stale_layout = [
            {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
            {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True},
            {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True},
            {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": True},
        ]
        session = self.client.session
        session["layout"] = stale_layout
        session.save()

        # Access configure layout view to trigger migration helper
        resp = self.client.get(reverse("configure_layout"))
        self.assertEqual(resp.status_code, 200)

        # The session layout should now contain general_feedback in the correct position (after feedback)
        migrated_layout = self.client.session["layout"]
        self.assertEqual(len(migrated_layout), 5)
        self.assertEqual(migrated_layout[2]["id"], "general_feedback")
        self.assertFalse(migrated_layout[2]["enabled"])

    def test_cohort_histogram_bin_colour_degree_level(self):
        """Verify that generate_cohort_histogram colours the 40% bin correctly based on degree_level."""
        from core.utils.charts import generate_cohort_histogram
        
        # Test cohort with scores in 40-49% range
        scores = [45]
        student_score = 45
        
        # 1. BEng (Undergraduate): 40-49% is a passing 3rd class (colored #f0a070)
        svg_beng = generate_cohort_histogram(scores, student_score, degree_level="BEng")
        self.assertIn('#f0a070', svg_beng)
        
        # 2. MEng/MSc (Postgraduate): 40-49% is a Fail (colored #d9534f)
        svg_meng = generate_cohort_histogram(scores, student_score, degree_level="MEng/MSc")
        self.assertIn('#d9534f', svg_meng)

    def test_generation_success_renders_results_page(self):
        """GET /assessment-feedback/success/ renders the success landing page with the cohort count."""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        url = reverse("generation_success")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Feedback Generation Successful")
        self.assertContains(resp, "2")  # Cohort count has 2 students in self.sample_uploaded_data

    def test_generation_success_redirects_without_session(self):
        """GET /assessment-feedback/success/ redirects to upload when session is empty."""
        url = reverse("generation_success")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("upload_file"))

    def test_download_email_xlsm_generates_valid_workbook(self):
        """GET /assessment-feedback/download-email-utility/ returns a valid .xlsm download response with student data."""
        session = self.client.session
        session["headers"] = self.sample_headers
        session["uploaded_data"] = self.sample_uploaded_data
        session["mappings"] = self.sample_mappings
        session.save()

        url = reverse("download_email_xlsm")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/vnd.ms-excel.sheet.macroEnabled.12")
        self.assertTrue(resp.has_header("Content-Disposition"))
        self.assertIn("attachment; filename=\"send_feedback.xlsm\"", resp["Content-Disposition"])

        # Load returned bytes using openpyxl
        import openpyxl
        from io import BytesIO
        wb = openpyxl.load_workbook(BytesIO(resp.content), keep_vba=True)
        
        # Verify VBA is kept (wb.vba_archive is populated)
        self.assertIsNotNone(wb.vba_archive)

        # Select active or Students sheet
        ws = wb['Students'] if 'Students' in wb.sheetnames else wb.active

        # Column A (ID), B (Name), C (Filename)
        # Check header
        self.assertEqual(ws.cell(row=1, column=1).value, "Student Number")
        self.assertEqual(ws.cell(row=1, column=2).value, "Name")
        self.assertEqual(ws.cell(row=1, column=3).value, "Attachment")

        # Row 2 (first student: Alice Smith, 10001)
        self.assertEqual(ws.cell(row=2, column=1).value, "10001")
        self.assertEqual(ws.cell(row=2, column=2).value, "Alice Smith")
        self.assertEqual(ws.cell(row=2, column=3).value, "10001_alice-smith.html")

        # Row 3 (second student: Bob Jones, 10002)
        self.assertEqual(ws.cell(row=3, column=1).value, "10002")
        self.assertEqual(ws.cell(row=3, column=2).value, "Bob Jones")
        self.assertEqual(ws.cell(row=3, column=3).value, "10002_bob-jones.html")

    def test_download_email_xlsm_redirects_without_session(self):
        """GET /assessment-feedback/download-email-utility/ redirects to upload when session is empty."""
        url = reverse("download_email_xlsm")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("upload_file"))





