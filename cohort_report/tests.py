import io
import openpyxl
import math
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from core.mcrf_parser import parse_mcrf_workbook
from cohort_report.views import compute_stats

class CohortReportTests(TestCase):
    def setUp(self):
        # Create a dummy MCRF Excel workbook in memory
        self.wb = openpyxl.Workbook()
        ws = self.wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append(["COMP3002 - Advanced Engineering Software"])
        ws.append(["", "", "CW1", "CW1", "Exam", "Exam"])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345678", "Alice Smith", 75, "A", 85, "A"])
        ws.append(["12345679/2", "Bob Jones", 45, "C", 55, "C"])
        ws.append(["w98765432", "Charlie Brown", 35, "F", 25, "F"])

        self.excel_bytes = io.BytesIO()
        self.wb.save(self.excel_bytes)
        self.excel_bytes.seek(0)

        # In-memory mock session data
        self.sample_uploaded_data = [
            {"Student ID": "w12345678", "Student Name": "Alice Smith", "CW1 - Mark": 75, "Exam - Mark": 85},
            {"Student ID": "12345679/2", "Student Name": "Bob Jones", "CW1 - Mark": 45, "Exam - Mark": 55},
            {"Student ID": "w98765432", "Student Name": "Charlie Brown", "CW1 - Mark": 35, "Exam - Mark": 25}
        ]
        self.sample_headers = ["Student ID", "Student Name", "CW1 - Mark", "Exam - Mark"]
        self.sample_mappings = {
            "col_student_name": "Student Name",
            "col_student_id": "Student ID",
            "degree_level": "BEng",
            "module_code": "COMP3002",
            "module_title": "Advanced Engineering Software",
            "components": [
                {"column": "CW1 - Mark", "max_marks": 100, "weight": 50, "type": "numeric"},
                {"column": "Exam - Mark", "max_marks": 100, "weight": 50, "type": "numeric"}
            ]
        }

    def test_compute_stats_undergraduate(self):
        """Verify undergraduate (BEng) statistics boundaries (Fail < 40%)"""
        scores = [75, 45, 35]
        stats = compute_stats(scores, degree_level="BEng")
        
        self.assertAlmostEqual(stats["mean"], 51.6666666, places=4)
        
        # Population standard deviation
        mean_val = sum(scores) / 3
        expected_var = sum((x - mean_val)**2 for x in scores) / 3
        expected_std = math.sqrt(expected_var)
        self.assertAlmostEqual(stats["std_dev"], expected_std, places=4)
        
        self.assertEqual(stats["max"], 75)
        self.assertEqual(stats["min"], 35)
        self.assertAlmostEqual(stats["pct_1st"], 33.3333333, places=4) # 75 is >= 70
        self.assertAlmostEqual(stats["pct_21_above"], 33.3333333, places=4) # 75 is >= 60
        self.assertAlmostEqual(stats["pct_fail"], 33.3333333, places=4) # 35 is < 40

    def test_compute_stats_postgraduate(self):
        """Verify postgraduate (MEng) statistics boundaries (Fail < 50%)"""
        scores = [75, 45, 35]
        stats = compute_stats(scores, degree_level="MEng/MSc")
        
        self.assertAlmostEqual(stats["pct_fail"], 66.6666666, places=4) # 45 and 35 are < 50

    def test_upload_cohort_data_get(self):
        """GET /cohort-report/upload/ returns 200 and renders upload template"""
        url = reverse("cohort_report_upload")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cohort Summary Report")
        self.assertContains(resp, "Analyse Cohort Data")

    def test_upload_cohort_data_post_redirects(self):
        """POST /cohort-report/upload/ with valid MCRF redirects to confirm mappings"""
        url = reverse("cohort_report_upload")
        uploaded_file = SimpleUploadedFile(
            "mcrf.xlsx", 
            self.excel_bytes.read(), 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        resp = self.client.post(url, {"file": uploaded_file})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("cohort_report_confirm"))
        
        # Assert sessions populated
        session = self.client.session
        self.assertIn("cohort_headers", session)
        self.assertIn("cohort_uploaded_data", session)
        self.assertIn("cohort_mappings", session)
        self.assertEqual(session["cohort_mappings"]["module_code"], "COMP3002")

    def test_confirm_cohort_mappings_post_valid(self):
        """POST /cohort-report/confirm/ saves valid mappings and weights summing to 100%"""
        session = self.client.session
        session["cohort_headers"] = self.sample_headers
        session["cohort_uploaded_data"] = self.sample_uploaded_data
        session["cohort_mappings"] = self.sample_mappings
        session.save()

        url = reverse("cohort_report_confirm")
        resp = self.client.post(url, {
            "module_code": "COMP3002-MOD",
            "module_title": "Software Systems Design",
            "degree_level": "MEng/MSc",
            "weight_0": "40",
            "weight_1": "60"
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("cohort_report_results"))

        # Verify session mappings updated, and student columns preserved
        updated_mappings = self.client.session["cohort_mappings"]
        self.assertEqual(updated_mappings["col_student_name"], "Student Name")
        self.assertEqual(updated_mappings["col_student_id"], "Student ID")
        self.assertEqual(updated_mappings["module_code"], "COMP3002-MOD")
        self.assertEqual(updated_mappings["degree_level"], "MEng/MSc")
        self.assertEqual(updated_mappings["components"][0]["weight"], 40)
        self.assertEqual(updated_mappings["components"][1]["weight"], 60)

    def test_confirm_cohort_mappings_post_invalid_sum(self):
        """POST /cohort-report/confirm/ fails if weights do not sum to 100%"""
        session = self.client.session
        session["cohort_headers"] = self.sample_headers
        session["cohort_uploaded_data"] = self.sample_uploaded_data
        session["cohort_mappings"] = self.sample_mappings
        session.save()

        url = reverse("cohort_report_confirm")
        resp = self.client.post(url, {
            "module_code": "COMP3002-MOD",
            "module_title": "Software Systems Design",
            "degree_level": "BEng",
            "weight_0": "30",
            "weight_1": "50" # Sum = 80
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Total component weight must sum to exactly 100%")

    def test_render_cohort_report_success(self):
        """GET /cohort-report/report/ computes performance stats and renders inline SVG charts"""
        session = self.client.session
        session["cohort_headers"] = self.sample_headers
        session["cohort_uploaded_data"] = self.sample_uploaded_data
        session["cohort_mappings"] = self.sample_mappings
        session.save()

        url = reverse("cohort_report_results")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "COMP3002")
        self.assertContains(resp, "Advanced Engineering Software")
        self.assertContains(resp, "Overall Module Performance")
        self.assertContains(resp, "<svg") # Inline SVG chart rendered

    def test_download_cohort_report(self):
        """GET /cohort-report/report/download/ returns standalone offline-ready attachment"""
        session = self.client.session
        session["cohort_headers"] = self.sample_headers
        session["cohort_uploaded_data"] = self.sample_uploaded_data
        session["cohort_mappings"] = self.sample_mappings
        session.save()

        url = reverse("cohort_report_download")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/html")
        self.assertIn("attachment; filename=", resp["Content-Disposition"])
        
        # Verify self-contained inline features
        content = resp.content.decode("utf-8")
        self.assertIn("<svg", content)
        self.assertIn(".report-header {", content) # Inline CSS styling verified
        self.assertNotIn("extends", content) # Standalone layout, no base templates

    def test_format_component_header(self):
        """Verify format_component_header successfully splits codes, names, and column types"""
        from cohort_report.views import format_component_header
        
        # With comp_names_map
        comp_names_map = {
            "001": "Industry compatible written submission (2500 words or equivalent)",
            "002": "Examination"
        }
        self.assertEqual(
            format_component_header("001 - Mark", comp_names_map),
            "001 - Industry compatible written submission (2500 words or equivalent)"
        )
        self.assertEqual(
            format_component_header("002 - Mark", comp_names_map),
            "002 - Examination"
        )
        self.assertEqual(
            format_component_header("001 - 30% - Mark", comp_names_map),
            "001 - Industry compatible written submission (2500 words or equivalent)"
        )
        
        # 3 parts fallback
        self.assertEqual(
            format_component_header("Industry compatible written submission (2500 words or equivalent) - 001 - Mark"),
            "001 - Industry compatible written submission (2500 words or equivalent)"
        )
        
        # 2 parts
        self.assertEqual(
            format_component_header("CW1 - Mark"),
            "CW1"
        )
        self.assertEqual(
            format_component_header("002 - Mark"),
            "002"
        )
        
        # 1 part
        self.assertEqual(
            format_component_header("Exam"),
            "Exam"
        )

    def test_mcrf_parser_numerical_code_descriptions(self):
        """Verify MCRF parser correctly handles integer/float code representations and multi-cell mapping rows"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append(["COMP3002 - Advanced Engineering Software"])
        ws.append([])
        ws.append([])
        ws.append(["Component", "Description", "", "", "", "Weighting"])
        # Rows mimicking the screenshot layout: Column A is integer, Column B is text description
        ws.append([1, "Industry compatible written submission (2500 words or equivalent)", "", "", "", "30%"])
        ws.append([2.0, "Timed online examination, (3 hours)", "", "", "", "70%"])
        ws.append([])
        ws.append([])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345678", "Alpha Student", 92, "A", 29, "F"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(buf)
        comp_names_map = module_info.get("comp_names_map", {})

        # Assert map contains normalized keys and correct descriptive titles (with length/duration stripped)
        self.assertEqual(
            comp_names_map.get("001"), 
            "Industry compatible written submission"
        )
        self.assertEqual(
            comp_names_map.get("002"), 
            "Timed online examination"
        )

