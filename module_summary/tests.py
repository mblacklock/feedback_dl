import io
import zipfile
import openpyxl
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from .views import normalize_student_id
from core.mcrf_parser import parse_mcrf_workbook


class ModuleSummaryViewsTest(TestCase):
    def setUp(self):
        # Create a dummy MCRF Excel workbook in memory
        self.wb_mcrf = openpyxl.Workbook()
        ws = self.wb_mcrf.active
        ws.append(["Module Marks Record Form (MCRF) - CIS3001"])
        ws.append([])
        ws.append(["", "", "CW1", "CW1", "Exam", "Exam"])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345678", "Alice Smith", 24, "A", 35, "B"])
        ws.append(["12345679/2", "Bob Jones", 18, "C", 28, "D"])

        # Save workbook to bytes
        self.excel_mcrf_bytes = io.BytesIO()
        self.wb_mcrf.save(self.excel_mcrf_bytes)
        self.excel_mcrf_bytes.seek(0)

        # In-memory mock parsed session data
        self.sample_uploaded_data = [
            {"Student ID": "w12345678", "Student Name": "Alice Smith", "CW1 - Mark": 24, "CW1 - Grade": "A", "Exam - Mark": 35, "Exam - Grade": "B"},
            {"Student ID": "12345679/2", "Student Name": "Bob Jones", "CW1 - Mark": 18, "CW1 - Grade": "C", "Exam - Mark": 28, "Exam - Grade": "D"}
        ]
        self.sample_headers = ["Student ID", "Student Name", "CW1 - Mark", "CW1 - Grade", "Exam - Mark", "Exam - Grade"]
        self.sample_mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "subdivision": "none",
            "components": [
                {"column": "CW1 - Mark", "max_marks": 100, "weight": 40, "type": "numeric"},
                {"column": "Exam - Mark", "max_marks": 100, "weight": 60, "type": "numeric"}
            ]
        }

    def test_normalize_student_id(self):
        """Verify the robust student number normalizer logic"""
        self.assertEqual(normalize_student_id("w12345678"), "w12345678")
        self.assertEqual(normalize_student_id("12345679/2"), "w12345679")
        self.assertEqual(normalize_student_id("S7654321A"), "7654321")
        self.assertEqual(normalize_student_id("   87654   "), "87654")
        self.assertEqual(normalize_student_id("abc"), "abc")
        self.assertEqual(normalize_student_id(None), "")

    def test_parse_mcrf_workbook(self):
        """Verify dynamic MCRF header discovery and row parsing"""
        self.excel_mcrf_bytes.seek(0)
        headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(self.excel_mcrf_bytes)
        
        self.assertTrue(is_mcrf)
        self.assertIn("CW1 - Mark", headers)
        self.assertIn("Exam - Grade", headers)
        self.assertEqual(len(data_rows), 2)
        self.assertEqual(data_rows[0]["Student ID"], "w12345678")
        self.assertEqual(data_rows[1]["CW1 - Mark"], 18)
        self.assertIsInstance(module_info, dict)

    def test_parse_mcrf_workbook_legacy_xls(self):
        """Verify dynamic MCRF parser works on legacy .xls files via xlrd fallback"""
        import os
        xls_path = r"c:\Backup Drive\Documents\django-apps\university\gradebook-merger\dummy_MCRF.xls"
        if os.path.exists(xls_path):
            with open(xls_path, "rb") as f:
                headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(f)
                
            self.assertTrue(is_mcrf)
            # Verify headers are processed and data rows are returned
            self.assertTrue(len(headers) > 0)
            self.assertTrue(len(data_rows) > 0)

    def test_upload_mcrf_get_renders_dropzone(self):
        """GET /module-summary/ returns 200 and renders dropzone"""
        url = reverse("module_upload")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Module Summary Sheet Generator")

    def test_upload_mcrf_post_redirects_to_confirm(self):
        """POST /module-summary/ with valid MCRF redirects to confirm mappings"""
        url = reverse("module_upload")
        self.excel_mcrf_bytes.seek(0)
        uploaded_file = SimpleUploadedFile("mcrf.xlsx", self.excel_mcrf_bytes.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        resp = self.client.post(url, {"file": uploaded_file})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("module_confirm"))
        
        # Check session populated
        self.assertIn("module_headers", self.client.session)
        self.assertIn("module_uploaded_data", self.client.session)
        self.assertIn("module_mappings", self.client.session)

    def test_confirm_module_mappings_get_renders_mappings(self):
        """GET /module-summary/confirm/ renders confirmation screen"""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        url = reverse("module_confirm")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Confirm MCRF Grade Mapping")
        self.assertContains(resp, "CW1 - Mark")

    def test_confirm_module_mappings_post_validates_weight_and_redirects(self):
        """POST /module-summary/confirm/ saves valid weights and redirects to layout"""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        url = reverse("module_confirm")
        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "weight_0": "40",
            "weight_1": "60"
        }
        
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("/module-summary/layout/"))

    def test_confirm_module_mappings_post_invalid_weight_renders_error(self):
        """POST /module-summary/confirm/ with invalid weights (sum != 100) displays error"""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        url = reverse("module_confirm")
        # weights sum to 90
        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "weight_0": "40",
            "weight_1": "50"
        }
        
        resp = self.client.post(url, form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Total component weight must sum to exactly 100%")

    def test_confirm_module_mappings_post_non_numeric_weight_renders_error(self):
        """POST /module-summary/mapping/ with a non-numeric weight should not raise a 500."""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "weight_0": "not-a-number",
            "weight_1": "60",
        }

        resp = self.client.post(reverse("module_confirm"), form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Validation Error")
        self.assertContains(resp, "Weight for CW1 - Mark must be a whole number between 0 and 100.")

    def test_confirm_module_mappings_post_weight_over_100_renders_error(self):
        """Individual component weights over 100 are rejected before processing."""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        form_data = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "weight_0": "101",
            "weight_1": "0",
        }

        resp = self.client.post(reverse("module_confirm"), form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Weight for CW1 - Mark must be a whole number between 0 and 100.")

    def test_upload_mcrf_with_no_component_marks_renders_error(self):
        """An uploaded workbook with no component mark columns should show an upload error."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append([])
        ws.append(["Student ID", "Student Name", "Grade", "Comment"])
        ws.append(["w12345678", "Alice Smith", "A", "No mark columns"])

        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        uploaded_file = SimpleUploadedFile(
            "no_mark_columns.xlsx",
            excel_bytes.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        resp = self.client.post(reverse("module_upload"), {"file": uploaded_file})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No component mark columns were detected")

    def test_configure_module_layout_get_renders_designer(self):
        """GET /module-summary/layout/ renders layout builder screen"""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        url = reverse("module_layout")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Module Summary Designer")
        self.assertContains(resp, "Summary Sheet Live Preview")

    def test_process_module_summary_generates_zip(self):
        """GET /module-summary/process/ aggregates data and streams ZIP containing HTML sheets"""
        session = self.client.session
        session["module_headers"] = self.sample_headers
        session["module_uploaded_data"] = self.sample_uploaded_data
        session["module_mappings"] = self.sample_mappings
        session.save()

        url = reverse("module_process")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        self.assertIn("attachment; filename=module_summary_reports.zip", resp["Content-Disposition"])

        # Validate ZIP content
        zip_bytes = io.BytesIO(resp.content)
        with zipfile.ZipFile(zip_bytes, "r") as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 2)
            self.assertIn("module_summary_w12345678_alice-smith.html", namelist)
            self.assertIn("module_summary_w12345679_bob-jones.html", namelist)
            
            # Verify HTML starts with DOCTYPE
            html_bytes = zf.read("module_summary_w12345678_alice-smith.html")
            self.assertTrue(html_bytes.startswith(b"<!DOCTYPE html>"))

    def test_mcrf_inference_with_header_weightings_and_blank_columns(self):
        """Verify MCRF auto-inference logic:
        1. Correctly handles empty header cells by naming them <Column X>.
        2. Only extracts components for 'Mark' columns, ignoring 'Grade'.
        3. Dynamically extracts weightings from header names (e.g. '001 - 30% - Mark').
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append([])
        ws.append(["", "", "CW1 - 30%", "CW1 - 30%", "Exam - 70%", "Exam - 70%"])
        ws.append(["Student ID", "", "Mark", "Grade", "Mark", "Grade"]) # Student Name header is empty!
        ws.append(["w12345678", "Alice Smith", 24, "A", 35, "B"])
        
        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        
        headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(excel_bytes)
        
        # 1. Empty student name header cell becomes '<Column B>'
        self.assertIn("<Column B>", headers)
        
        # 2. Mock session upload flow to test auto-inference mapping
        url = reverse("module_upload")
        excel_bytes.seek(0)
        uploaded_file = SimpleUploadedFile("mcrf_weights.xlsx", excel_bytes.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        # POST file to trigger auto-inference
        self.client.post(url, {"file": uploaded_file})
        
        # Check auto-inferred session mappings
        mappings = self.client.session["module_mappings"]
        
        # 3. Only Mark columns parsed as components, Grade columns ignored
        components = mappings["components"]
        component_cols = [c["column"] for c in components]
        
        self.assertIn("CW1 - 30% - Mark", component_cols)
        self.assertIn("Exam - 70% - Mark", component_cols)
        self.assertNotIn("CW1 - 30% - Grade", component_cols)
        self.assertNotIn("Exam - 70% - Grade", component_cols)
        
        # 4. Weightings are correctly extracted from header names!
        cw1_comp = next(c for c in components if c["column"] == "CW1 - 30% - Mark")
        exam_comp = next(c for c in components if c["column"] == "Exam - 70% - Mark")
        
        self.assertEqual(cw1_comp["weight"], 30)
        self.assertEqual(exam_comp["weight"], 70)
