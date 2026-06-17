import io
import openpyxl
import json
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from programme_analytics.views import (
    infer_module_level,
    calculate_module_analytics,
)


class ProgrammeAnalyticsTests(TestCase):
    def setUp(self):
        # Create a dummy MCRF Excel workbook in memory
        self.wb = openpyxl.Workbook()
        ws = self.wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append(["COMP5034 - Object Oriented Programming"])
        ws.append(["", "", "CW1", "CW1", "Exam", "Exam"])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345678", "Alice Smith", 75, "A", 85, "A"])
        ws.append(["12345679/2", "Bob Jones", 45, "C", 55, "C"])
        ws.append(["w98765432", "Charlie Brown", 35, "F", 25, "F"])

        self.excel_bytes = io.BytesIO()
        self.wb.save(self.excel_bytes)
        self.excel_bytes.seek(0)

        # Pre-populate session data for confirm test
        self.sample_uploaded_modules = [
            {
                'filename': 'COMP5034.xlsx',
                'module_code': 'COMP5034',
                'module_title': 'Object Oriented Programming',
                'detected_level': 5,
                'scores': [80, 50, 30],
                'year': '2025/26',
                'period': 'SEM1',
                'occurrence': 'BNN',
                'components': [
                    {
                        'column': 'CW1 (50%)',
                        'weight': 50,
                        'scores': [75, 45, 35],
                        'detected_category': 'Individual CW'
                    }
                ]
            }
        ]

    def test_infer_module_level(self):
        """Verify module levels are inferred correctly from the code."""
        self.assertEqual(infer_module_level('KB4001'), 4)
        self.assertEqual(infer_module_level('KB5034'), 5)
        self.assertEqual(infer_module_level('EE6002'), 6)
        self.assertEqual(infer_module_level('ME7002'), 7)
        self.assertEqual(infer_module_level('INVALID'), 4)
        self.assertEqual(infer_module_level(''), 4)

    def test_calculate_module_analytics_ug(self):
        """Verify undergraduate metrics (Level < 7) use a 40% fail threshold and correct bins."""
        scores = [80, 50, 30] # Mean = 53.3, Fail (30) is 33.3%, 1st (80) is 33.3%
        stats = calculate_module_analytics(scores, level=5)
        
        self.assertAlmostEqual(stats["mean"], 53.3333333)
        self.assertAlmostEqual(stats["median"], 50.0)
        self.assertAlmostEqual(stats["pct_1st"], 33.3333333)
        self.assertAlmostEqual(stats["pct_fail"], 33.3333333) # 30 is < 40
        self.assertAlmostEqual(stats["pct_21_above"], 33.3333333) # only 80 is >= 60
        self.assertEqual(stats["cohort_size"], 3)
        self.assertEqual(stats["max"], 80)
        self.assertEqual(stats["min"], 30)
        self.assertEqual(stats["score_bins"]["absent"], 0)
        self.assertEqual(stats["score_bins"]["bins"], [0, 0, 0, 1, 0, 1, 0, 0, 1, 0])

    def test_calculate_module_analytics_pg(self):
        """Verify postgraduate metrics (Level >= 7) use a 50% fail threshold, and check bins with an absent student."""
        scores = [80, 50, 45, 0] # Mean = 43.75, Fails are 45 and 0 (both < 50 for PG) -> 50% fail
        stats = calculate_module_analytics(scores, level=7)
        
        self.assertAlmostEqual(stats["pct_fail"], 50.0)
        self.assertAlmostEqual(stats["pct_21_above"], 25.0) # 80 is >= 60
        self.assertAlmostEqual(stats["pct_1st"], 25.0) # 80 is >= 70
        self.assertEqual(stats["max"], 80)
        self.assertEqual(stats["min"], 0)
        self.assertEqual(stats["score_bins"]["absent"], 1)
        self.assertEqual(stats["score_bins"]["bins"], [0, 0, 0, 0, 1, 1, 0, 0, 1, 0])

    def test_calculate_module_analytics_empty(self):
        """Verify analytics behaves cleanly when scores is empty."""
        stats = calculate_module_analytics([], level=5)
        self.assertEqual(stats["mean"], 0.0)
        self.assertEqual(stats["cohort_size"], 0)
        self.assertEqual(stats["max"], 0.0)
        self.assertEqual(stats["min"], 0.0)
        self.assertEqual(stats["score_bins"]["absent"], 0)
        self.assertEqual(stats["score_bins"]["bins"], [0] * 10)

    def test_analytics_upload_get(self):
        """GET /programme-analytics/ returns 200 and renders upload screen."""
        url = reverse("analytics_upload")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Programme Analytics")
        self.assertContains(resp, "Upload and Map Modules")

    def test_analytics_upload_post_redirects(self):
        """POST /programme-analytics/ with valid MCRF redirects to confirm."""
        url = reverse("analytics_upload")
        uploaded_file = SimpleUploadedFile(
            "COMP5034.xlsx", 
            self.excel_bytes.read(), 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        resp = self.client.post(url, {"files": [uploaded_file]})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_confirm"))
        
        session = self.client.session
        self.assertIn("analytics_uploaded_modules", session)
        self.assertEqual(len(session["analytics_uploaded_modules"]), 1)
        self.assertEqual(session["analytics_uploaded_modules"][0]["module_code"], "COMP5034")

    def test_analytics_confirm_post_redirects(self):
        """POST /programme-analytics/confirm/ saves confirmed details and redirects to dashboard."""
        session = self.client.session
        session["analytics_uploaded_modules"] = self.sample_uploaded_modules
        session.save()

        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "COMP5034-MOD",
            "title_0": "Object-Oriented Programming (Modified)",
            "level_0": "5",
            "comp_cat_0_0": "Individual CW"
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_dashboard"))

        confirmed = self.client.session["analytics_confirmed_data"]
        self.assertEqual(confirmed["programme_name"], "BEng Computer Science")
        self.assertEqual(confirmed["modules"][0]["module_code"], "COMP5034-MOD")
        self.assertEqual(confirmed["modules"][0]["level"], 5)
        self.assertEqual(confirmed["modules"][0]["components"][0]["category"], "Individual CW")

    def test_analytics_dashboard_renders(self):
        """GET /programme-analytics/dashboard/ renders the full comparison and distributions."""
        session = self.client.session
        session["analytics_confirmed_data"] = {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "modules": [
                {
                    'module_code': 'COMP5034',
                    'module_title': 'Object Oriented Programming',
                    'level': 5,
                    'scores': [80, 50, 30],
                    'mean': 53.33,
                    'median': 50.0,
                    'std_dev': 20.5,
                    'pct_1st': 33.3,
                    'pct_21_above': 33.3,
                    'pct_fail': 33.3,
                    'cohort_size': 3,
                    'components': [
                        {
                            'column': 'CW1',
                            'weight': 50,
                            'scores': [80, 50, 30],
                            'category': 'Individual CW'
                        }
                    ]
                }
            ]
        }
        session.save()

        url = reverse("analytics_dashboard")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "COMP5034")
        self.assertContains(resp, "BEng Computer Science")
        self.assertContains(resp, "Module Means Comparison")
        self.assertContains(resp, "Normalised Overlay")
        self.assertContains(resp, "Component Heatmap")
        self.assertContains(resp, "Level Benchmarking")
        self.assertContains(resp, "<svg")

    def test_download_snapshot(self):
        """GET /programme-analytics/download/ exports anonymised JSON snapshot."""
        session = self.client.session
        session["analytics_confirmed_data"] = {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "modules": [
                {
                    'module_code': 'COMP5034',
                    'module_title': 'Object Oriented Programming',
                    'level': 5,
                    'scores': [80, 50, 30],
                    'mean': 53.33,
                    'median': 50.0,
                    'std_dev': 20.5,
                    'pct_1st': 33.3,
                    'pct_21_above': 33.3,
                    'pct_fail': 33.3,
                    'cohort_size': 3
                }
            ]
        }
        session.save()

        url = reverse("download_snapshot")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assertIn("attachment; filename=", resp["Content-Disposition"])
        
        data = json.loads(resp.content)
        self.assertEqual(data["programme"], "BEng Computer Science")
        self.assertEqual(data["modules"][0]["code"], "COMP5034")
        self.assertIn("score_bins", data["modules"][0])
        self.assertEqual(data["modules"][0]["score_bins"]["absent"], 0)
        self.assertEqual(data["modules"][0]["score_bins"]["bins"], [0, 0, 0, 1, 0, 1, 0, 0, 1, 0])

    def test_analytics_modules_sorting(self):
        """Verify uploaded and confirmed modules are sorted alphabetically by code."""
        # Setup multiple modules unsorted in session
        unsorted_modules = [
            {'filename': 'EE6002.xlsx', 'module_code': 'EE6002', 'module_title': 'Electronics', 'detected_level': 6, 'scores': [60]},
            {'filename': 'COMP5034.xlsx', 'module_code': 'COMP5034', 'module_title': 'OOP', 'detected_level': 5, 'scores': [70]},
            {'filename': 'KB4001.xlsx', 'module_code': 'KB4001', 'module_title': 'Maths', 'detected_level': 4, 'scores': [50]},
        ]
        
        session = self.client.session
        session["analytics_uploaded_modules"] = list(unsorted_modules)
        session.save()
        
        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "EE6002",
            "title_0": "Electronics",
            "level_0": "6",
            "code_1": "COMP5034",
            "title_1": "OOP",
            "level_1": "5",
            "code_2": "KB4001",
            "title_2": "Maths",
            "level_2": "4"
        })
        self.assertEqual(resp.status_code, 302)
        
        # Verify saved confirmed data is sorted: COMP5034, EE6002, KB4001
        confirmed = self.client.session["analytics_confirmed_data"]
        modules = confirmed["modules"]
        self.assertEqual(len(modules), 3)
        self.assertEqual(modules[0]["module_code"], "COMP5034")
        self.assertEqual(modules[1]["module_code"], "EE6002")
        self.assertEqual(modules[2]["module_code"], "KB4001")

    def test_auto_detect_component_category(self):
        """Verify component type detection rules."""
        from programme_analytics.views import auto_detect_component_category
        self.assertEqual(auto_detect_component_category("Exam CW1"), "Exam")
        self.assertEqual(auto_detect_component_category("Final Exam"), "Exam")
        self.assertEqual(auto_detect_component_category("Timed online examination"), "Exam")
        self.assertEqual(auto_detect_component_category("written examinations"), "Exam")
        self.assertEqual(auto_detect_component_category("example sheet"), "Individual CW")
        self.assertEqual(auto_detect_component_category("presentation slides"), "Presentation")
        self.assertEqual(auto_detect_component_category("Group coursework 1"), "Group CW")
        self.assertEqual(auto_detect_component_category("portfolio of essays"), "Portfolio")
        self.assertEqual(auto_detect_component_category("Regular report"), "Individual CW")

    def test_category_auto_detection_with_description(self):
        """Verify that category auto-detection successfully extracts code and looks up description."""
        import re
        from programme_analytics.views import auto_detect_component_category
        
        col_name = "001 - Mark"
        comp_names_map = {"001": "Oral Presentation (10-20min)"}
        
        description = ""
        code_match = re.search(r'\b(\d{1,3}|CW\d|EX\d|EXAM\d?)\b', col_name, re.IGNORECASE)
        if code_match:
            code = code_match.group(1)
            s = str(code).strip().split('.')[0]
            code_norm = f"{int(s):03d}" if s.isdigit() else s.upper()
            description = comp_names_map.get(code_norm, "")
            
        search_str = f"{col_name} - {description}" if description else col_name
        category = auto_detect_component_category(search_str)
        self.assertEqual(category, "Presentation")

    def test_credits_and_student_scores_in_upload_session(self):
        """Verify analytics_upload saves detected_credits and student_scores to session."""
        url = reverse("analytics_upload")
        uploaded_file = SimpleUploadedFile(
            "COMP5034.xlsx", 
            self.excel_bytes.read(), 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp = self.client.post(url, {"files": [uploaded_file]})
        self.assertEqual(resp.status_code, 302)
        
        uploaded = self.client.session["analytics_uploaded_modules"][0]
        self.assertEqual(uploaded["detected_credits"], 20)
        self.assertTrue(len(uploaded["student_scores"]) > 0)
        
        # Verify student hashes are 64-character hex strings (SHA-256)
        first_hash = list(uploaded["student_scores"].keys())[0]
        self.assertEqual(len(first_hash), 64)

    def test_analytics_confirm_saves_credits(self):
        """Verify that analytics_confirm processes submitted credits and maps student_scores."""
        session = self.client.session
        session["analytics_uploaded_modules"] = self.sample_uploaded_modules
        # populate simulated student_scores
        session["analytics_uploaded_modules"][0]["student_scores"] = {
            "test_hash_1": 80,
            "test_hash_2": 50,
        }
        session.save()

        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "COMP5034-MOD",
            "title_0": "Object-Oriented Programming (Modified)",
            "level_0": "5",
            "credits_0": "15",
            "comp_cat_0_0": "Individual CW"
        })
        self.assertEqual(resp.status_code, 302)

        confirmed = self.client.session["analytics_confirmed_data"]
        self.assertEqual(confirmed["modules"][0]["credits"], 15)
        self.assertEqual(confirmed["modules"][0]["detected_credits"], 15)
        self.assertEqual(confirmed["modules"][0]["student_scores"]["test_hash_1"], 80)

    def test_credit_weighted_student_level_aggregation(self):
        """Verify credit-weighted level aggregates calculations are correct."""
        session = self.client.session
        # Setup a student "student_A" taking two modules:
        # Module 1: 10 credits, score 80
        # Module 2: 20 credits, score 50
        # Expected credit-weighted average: (80*10 + 50*20) / (10+20) = 1800 / 30 = 60.0%
        
        # Setup student "student_B" taking one module:
        # Module 2: 20 credits, score 50
        # Expected credit-weighted average: 50.0%
        
        session["analytics_confirmed_data"] = {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "modules": [
                {
                    'module_code': 'COMP5001',
                    'module_title': 'Programming 1',
                    'level': 5,
                    'credits': 10,
                    'scores': [80],
                    'student_scores': {
                        "student_A_hash": 80
                    },
                    'components': []
                },
                {
                    'module_code': 'COMP5002',
                    'module_title': 'Programming 2',
                    'level': 5,
                    'credits': 20,
                    'scores': [50, 50],
                    'student_scores': {
                        "student_A_hash": 50,
                        "student_B_hash": 50
                    },
                    'components': []
                }
            ]
        }
        session.save()

        url = reverse("analytics_dashboard")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        level_aggregates = resp.context["level_aggregates"]
        # Find level 5 aggregate
        lvl5_agg = next(item for item in level_aggregates if item["level"] == 5)
        
        # Unique students at level 5: student_A and student_B (cohort size = 2)
        self.assertEqual(lvl5_agg["cohort_size"], 2)
        # student_A weighted avg: 60.0%, student_B: 50.0%
        # Cohort mean: (60.0 + 50.0) / 2 = 55.0%
        self.assertAlmostEqual(lvl5_agg["mean"], 55.0)
