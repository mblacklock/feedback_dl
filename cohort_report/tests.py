import io
import openpyxl
import math
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from core.mcrf_parser import parse_mcrf_workbook
from cohort_report.views import compute_stats, pearson_correlation

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
            {"Student ID": "w98765432", "Student Name": "Charlie Brown", "CW1 - Mark": 35, "Exam - Mark": 25},
            {"Student ID": "w00000000", "Student Name": "No Show 1", "CW1 - Mark": 0, "Exam - Mark": 90},
            {"Student ID": "w11111111", "Student Name": "No Show 2", "CW1 - Mark": 60, "Exam - Mark": 0}
        ]
        self.sample_headers = ["Student ID", "Student Name", "CW1 - Mark", "Exam - Mark"]
        self.sample_mappings = {
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

        # Verify session mappings updated
        updated_mappings = self.client.session["cohort_mappings"]
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

    def test_pass_fail_component_exclusion(self):
        """Verify that components with 0% weight are excluded from the cohort report's components_stats."""
        session = self.client.session
        session["cohort_headers"] = ["Student ID", "Student Name", "CW1 - Mark", "PassFail - Mark"]
        session["cohort_uploaded_data"] = [
            {"Student ID": "w12345678", "Student Name": "Alice Smith", "CW1 - Mark": 75, "PassFail - Mark": 100},
            {"Student ID": "12345679/2", "Student Name": "Bob Jones", "CW1 - Mark": 45, "PassFail - Mark": 100},
        ]
        session["cohort_mappings"] = {
            "degree_level": "BEng",
            "module_code": "COMP3002",
            "module_title": "Advanced Engineering Software",
            "components": [
                {"column": "CW1 - Mark", "max_marks": 100, "weight": 100, "type": "numeric"},
                {"column": "PassFail - Mark", "max_marks": 100, "weight": 0, "type": "numeric"}
            ]
        }
        session.save()

        url = reverse("cohort_report_results")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        components_stats = resp.context["components_stats"]
        # The 0% weight component should be excluded from components_stats
        self.assertEqual(len(components_stats), 1)
        self.assertEqual(components_stats[0]["column"], "CW1 - Mark")

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_pdf_mcrf_cohort_report(self, mock_pdf_reader):
        """Verify that a PDF MCRF file can be uploaded and processed in the cohort report app."""
        from unittest.mock import MagicMock
        
        mock_layout_text = (
            "                                                   Faculty of Science and Environment\n"
            "                                                   Module Marks Record Form (MCRF)\n"
            "                                                                       First Sit\n"
            "Module           KB7071 - Wind, Photovoltaic and Hybrid                              Tutor        Dr Maryam Bayati\n"
            "                 Renewable Energy Systems\n"
            "Year             2025/6                                                              Credits      20\n"
            "Period           SEM1                                                                Level        7\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne                          Location     Newcastle upon Tyne\n"
            "                 FNN: January start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Individual report (2,500 words or equivalent)                                                                                           30%\n"
            "002           Individual report (3,500 words or equivalent)                                                                                           70%\n"
            "\n"
            "                                                                                001 - 30%     002 - 70%        Module\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            "\n"
            "11111111/1    SMITH, ALICE                              FNN       SEM1         60      P      77      P      72      P\n"
            "\n"
            "22222222/1    BROWN, ROBERT                             FNN       SEM1         79      P      76     PX      77      P\n"
            "              WILLIAM JOHN\n"
        )
        
        mock_page = MagicMock()
        mock_page.extract_text.return_value = mock_layout_text
        mock_pdf_reader.return_value.pages = [mock_page]
        
        uploaded_file = SimpleUploadedFile(
            "sample_mcrf.pdf",
            b"%PDF-1.4\n%mocked pdf bytes",
            content_type="application/pdf"
        )
        
        url = reverse("cohort_report_upload")
        # Post the PDF file
        resp = self.client.post(url, {"file": uploaded_file})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("cohort_report_confirm"))
        
        # Verify session mappings populated
        session = self.client.session
        self.assertIn("cohort_headers", session)
        self.assertIn("cohort_uploaded_data", session)
        self.assertIn("cohort_mappings", session)
        self.assertEqual(session["cohort_mappings"]["module_code"], "KB7071")
        self.assertEqual(session["cohort_mappings"]["module_title"], "Wind, Photovoltaic and Hybrid Renewable Energy Systems")
        self.assertEqual(session["cohort_mappings"]["year"], "2025/26")
        self.assertEqual(session["cohort_mappings"]["period"], "SEM1")
        self.assertEqual(session["cohort_mappings"]["occurrence"], "BNN/FNN")

    def test_pearson_correlation_calculation(self):
        """Verify the pearson_correlation function behaves correctly under all conditions"""
        # Strong positive correlation
        x = [10, 20, 30, 40]
        y = [15, 25, 35, 45]
        self.assertAlmostEqual(pearson_correlation(x, y), 1.0)

        # Strong negative correlation
        x = [10, 20, 30, 40]
        y = [45, 35, 25, 15]
        self.assertAlmostEqual(pearson_correlation(x, y), -1.0)

        # Less than 3 points
        x = [10, 20]
        y = [20, 30]
        self.assertIsNone(pearson_correlation(x, y))

        # Zero variance (standard deviation)
        x = [50, 50, 50, 50]
        y = [10, 20, 30, 40]
        self.assertIsNone(pearson_correlation(x, y))

    def test_component_correlation_rendering(self):
        """Verify that within-module component correlation scatter plots are generated and rendered properly, excluding non-submissions (0% marks)"""
        session = self.client.session
        session["cohort_headers"] = self.sample_headers
        session["cohort_uploaded_data"] = self.sample_uploaded_data
        session["cohort_mappings"] = self.sample_mappings
        session.save()

        url = reverse("cohort_report_results")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Verify scatter context parameters
        self.assertIn("scatter_charts", resp.context)
        self.assertIn("fail_threshold", resp.context)
        
        # Check active components are paired
        charts = resp.context["scatter_charts"]
        self.assertEqual(len(charts), 1) # 1 pair for 2 active components
        self.assertEqual(charts[0]["comp_x"], "CW1")
        self.assertEqual(charts[0]["comp_y"], "Exam")
        
        # Check specific Pearson value for mock data:
        # CW1 marks: [75, 45, 35], Exam marks: [85, 55, 25]
        # Pearson correlation between [75, 45, 35] and [85, 55, 25] is approx 0.9607689
        self.assertAlmostEqual(charts[0]["r"], 0.9607689, places=5)
        self.assertIn("<svg", charts[0]["chart_svg"])
        
        # Verify both normal points (blue #3b82f6) and zero points (red #ef4444) exist in the SVG
        self.assertIn("#3b82f6", charts[0]["chart_svg"])
        self.assertIn("#ef4444", charts[0]["chart_svg"])

        # Confirm the page renders the scatter plots section
        self.assertContains(resp, "Assessment Component Correlations")
        self.assertContains(resp, "CW1 vs Exam")
        self.assertContains(resp, "0.96")

        # Test download template as well
        download_url = reverse("cohort_report_download")
        download_resp = self.client.get(download_url)
        self.assertEqual(download_resp.status_code, 200)
        
        content = download_resp.content.decode("utf-8")
        self.assertIn("Assessment Component Correlations", content)
        self.assertIn("CW1 vs Exam", content)
        self.assertIn("0.96", content)


