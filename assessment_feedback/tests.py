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
        self.assertTrue(resp.url.endswith("/assessment-feedback/process/"))

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
