import io
import openpyxl
import json
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

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
                        'weight': 100,
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
        
        # Verify that level_aggregates and modules are correctly populated
        self.assertIn("level_aggregates", resp.context)
        self.assertIn("modules", resp.context)
        
        lvl5_agg = next(item for item in resp.context["level_aggregates"] if item["level"] == 5)
        self.assertEqual(lvl5_agg["modules_count"], 1)
        self.assertEqual(lvl5_agg["cohort_size"], 3)
        self.assertAlmostEqual(lvl5_agg["mean"], 53.33, places=2)
        
        modules = resp.context["modules"]
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["module_code"], "COMP5034")
        self.assertAlmostEqual(modules[0]["mean"], 53.33, places=2)
        self.assertEqual(modules[0]["cohort_size"], 3)


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

    def test_credits_in_upload_session(self):
        """Verify analytics_upload saves detected_credits to session."""
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

    def test_analytics_confirm_saves_credits(self):
        """Verify that analytics_confirm processes submitted credits."""
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
            "credits_0": "15",
            "comp_cat_0_0": "Individual CW"
        })
        self.assertEqual(resp.status_code, 302)

        confirmed = self.client.session["analytics_confirmed_data"]
        self.assertEqual(confirmed["modules"][0]["credits"], 15)
        self.assertEqual(confirmed["modules"][0]["detected_credits"], 15)

    def test_level_aggregation(self):
        """Verify level aggregates calculation correctly pools module scores at that level and counts unique student IDs."""
        session = self.client.session
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
                    'student_ids': ['S001'],
                    'components': []
                },
                {
                    'module_code': 'COMP5002',
                    'module_title': 'Programming 2',
                    'level': 5,
                    'credits': 20,
                    'scores': [50, 50],
                    'student_ids': ['S001', 'S002'],
                    'components': []
                },
                {
                    'module_code': 'COMP3001',
                    'module_title': 'Foundation Maths',
                    'level': 3,
                    'credits': 20,
                    'scores': [60, 70],
                    'student_ids': ['S003', 'S004'],
                    'components': []
                }
            ]
        }
        session.save()

        url = reverse("analytics_dashboard")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        level_aggregates = resp.context["level_aggregates"]
        lvl5_agg = next(item for item in level_aggregates if item["level"] == 5)
        
        # Unique student IDs at level 5: 'S001', 'S002' -> cohort size 2
        self.assertEqual(lvl5_agg["cohort_size"], 2)
        # Cohort mean: (80 + 50 + 50) / 3 = 60.0%
        self.assertAlmostEqual(lvl5_agg["mean"], 60.0)

        lvl3_agg = next(item for item in level_aggregates if item["level"] == 3)
        # Unique student IDs at level 3: 'S003', 'S004' -> cohort size 2
        self.assertEqual(lvl3_agg["cohort_size"], 2)
        # Cohort mean: (60 + 70) / 2 = 65.0%
        self.assertAlmostEqual(lvl3_agg["mean"], 65.0)

    def test_normalize_snapshot(self):
        """Verify normalize_snapshot standardizes session modules and snapshot JSON formats."""
        from programme_analytics.views import normalize_snapshot
        
        # Test format 1 (snapshot format)
        snap1 = {
            'programme': 'CS',
            'year': '2023/24',
            'modules': [
                {
                    'code': 'CS101',
                    'title': 'Intro',
                    'level': 4,
                    'credits': 20,
                    'mean': 60.0,
                    'std_dev': 12.5,
                    'grade_dist': {'pct_1st': 10.0, 'pct_fail': 5.0, 'pct_21_above': 60.0},
                    'n': 50
                }
            ]
        }
        norm1 = normalize_snapshot(snap1)
        self.assertEqual(norm1['programme'], 'CS')
        self.assertEqual(norm1['year'], '2023/24')
        self.assertEqual(len(norm1['modules']), 1)
        self.assertEqual(norm1['modules'][0]['code'], 'CS101')
        self.assertEqual(norm1['modules'][0]['std_dev'], 12.5)
        self.assertEqual(norm1['modules'][0]['pct_1st'], 10.0)
        self.assertEqual(norm1['modules'][0]['pct_21_above'], 60.0)
        self.assertEqual(norm1['modules'][0]['pct_fail'], 5.0)
        self.assertEqual(norm1['modules'][0]['n'], 50)
        
        # Test format 2 (session/alternate format)
        snap2 = {
            'programme_name': 'CS',
            'academic_year': '2023/24',
            'modules': [
                {
                    'module_code': 'CS101',
                    'module_title': 'Intro',
                    'level': 4,
                    'detected_credits': 20,
                    'mean': 60.0,
                    'std_dev': 12.5,
                    'pct_1st': 10.0,
                    'pct_21_above': 60.0,
                    'pct_fail': 5.0,
                    'cohort_size': 50
                }
            ]
        }
        norm2 = normalize_snapshot(snap2)
        self.assertEqual(norm2['modules'][0]['code'], 'CS101')
        self.assertEqual(norm2['modules'][0]['std_dev'], 12.5)
        self.assertEqual(norm2['modules'][0]['pct_1st'], 10.0)
        self.assertEqual(norm2['modules'][0]['pct_21_above'], 60.0)
        self.assertEqual(norm2['modules'][0]['pct_fail'], 5.0)
        self.assertEqual(norm2['modules'][0]['n'], 50)

    def test_upload_snapshots_valid(self):
        """POST upload_snapshots with a valid JSON snapshot stores normalized snap in session."""
        snap_data = {
            'programme': 'BEng Computer Science',
            'year': '2024/25',
            'modules': [
                {
                    'code': 'CS101',
                    'title': 'Intro to CS',
                    'level': 4,
                    'credits': 20,
                    'mean': 62.5,
                    'std_dev': 11.2,
                    'grade_dist': {'pct_1st': 15.0, 'pct_fail': 8.0, 'pct_21_above': 65.0},
                    'n': 40
                }
            ]
        }
        snap_file = SimpleUploadedFile(
            "snapshot_2024_25.json",
            json.dumps(snap_data).encode('utf-8'),
            content_type="application/json"
        )
        
        url = reverse("upload_snapshots")
        resp = self.client.post(url, {"snapshots": [snap_file]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("#trends"))
        
        session = self.client.session
        self.assertIn("analytics_historical_snapshots", session)
        snapshots = session["analytics_historical_snapshots"]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]['year'], '2024/25')
        self.assertEqual(snapshots[0]['modules'][0]['code'], 'CS101')

    def test_upload_snapshots_invalid(self):
        """POST upload_snapshots with an invalid file sets trends_error in session."""
        bad_file = SimpleUploadedFile(
            "bad.json",
            b"invalid json content",
            content_type="application/json"
        )
        
        url = reverse("upload_snapshots")
        resp = self.client.post(url, {"snapshots": [bad_file]})
        self.assertEqual(resp.status_code, 302)
        
        session = self.client.session
        self.assertIn("trends_error", session)
        self.assertIn("is not a valid JSON file", session["trends_error"])

    def test_clear_snapshots(self):
        """POST clear_snapshots clears snapshots and errors from session."""
        session = self.client.session
        session["analytics_historical_snapshots"] = [{"year": "2024/25"}]
        session["trends_error"] = "Some error"
        session.save()
        
        url = reverse("clear_snapshots")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        
        session = self.client.session
        self.assertNotIn("analytics_historical_snapshots", session)
        self.assertNotIn("trends_error", session)

    def test_analytics_dashboard_with_trends(self):
        """GET dashboard with historical snapshots calculates trend data structure."""
        # 1. Setup confirmed current cohort data in session (Year 2025/26)
        session = self.client.session
        session["analytics_confirmed_data"] = {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "modules": [
                {
                    'module_code': 'CS101',
                    'module_title': 'Intro to CS',
                    'level': 4,
                    'credits': 20,
                    'scores': [70, 50],  # Mean = 60%, 1st = 50%, Fail = 0%
                    'mean': 60.0,
                    'median': 60.0,
                    'std_dev': 10.0,
                    'pct_1st': 50.0,
                    'pct_21_above': 50.0,
                    'pct_fail': 0.0,
                    'cohort_size': 2,
                    'components': []
                }
            ]
        }
        
        # 2. Setup historical snapshot in session (Year 2024/25)
        session["analytics_historical_snapshots"] = [
            {
                'programme': 'BEng Computer Science',
                'year': '2024/25',
                'modules': [
                    {
                        'code': 'CS101',
                        'title': 'Intro to CS',
                        'level': 4,
                        'credits': 20,
                        'mean': 55.0,
                        'std_dev': 8.0,
                        'pct_1st': 20.0,
                        'pct_fail': 10.0,
                        'pct_21_above': 60.0,
                        'n': 10
                    }
                ]
            }
        ]
        session.save()
        
        # 3. GET dashboard
        url = reverse("analytics_dashboard")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        
        # Verify trends_data context
        self.assertIn("trends_data", resp.context)
        trends_data = resp.context["trends_data"]
        self.assertEqual(trends_data['years'], ['2024/25', '2025/26'])
        self.assertEqual(len(trends_data['module_trends']), 1)
        
        # Check module CS101 trend values
        m_trend = trends_data['module_trends'][0]
        self.assertEqual(m_trend['code'], 'CS101')
        self.assertTrue(m_trend['has_history'])
        self.assertIn('<svg', m_trend['sparkline_svg'])
        
        # Verify year_columns details
        year_cols = m_trend['year_columns']
        self.assertEqual(len(year_cols), 2)
        
        self.assertEqual(year_cols[0]['year'], '2024/25')
        self.assertEqual(year_cols[0]['mean'], 55.0)
        self.assertEqual(year_cols[0]['pct_1st'], 20.0)
        self.assertEqual(year_cols[0]['pct_fail'], 10.0)
        self.assertEqual(year_cols[0]['n'], 10)
        self.assertTrue(year_cols[0]['present'])
        
        self.assertEqual(year_cols[1]['year'], '2025/26')
        self.assertEqual(year_cols[1]['mean'], 60.0)
        self.assertEqual(year_cols[1]['pct_1st'], 50.0)
        self.assertEqual(year_cols[1]['pct_fail'], 0.0)
        self.assertEqual(year_cols[1]['n'], 2)
        self.assertTrue(year_cols[1]['present'])


    def test_pass_fail_component_exclusion(self):
        """Verify that components with 0% weight are excluded from components_stats and heatmap_cells."""
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
                            'column': 'CW1 (100%)',
                            'weight': 100,
                            'scores': [80, 50, 30],
                            'category': 'Individual CW'
                        },
                        {
                            'column': 'PassFail (0%)',
                            'weight': 0,
                            'scores': [100, 100, 100],
                            'category': 'Exam'
                        }
                    ]
                }
            ]
        }
        session.save()

        url = reverse("analytics_dashboard")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Retrieve processed modules from the context
        modules = resp.context["modules"]
        self.assertEqual(len(modules), 1)
        m = modules[0]

        # 0% weight component should not be in components_stats
        self.assertEqual(len(m['components_stats']), 1)
        self.assertEqual(m['components_stats'][0]['column'], 'CW1 (100%)')

        # 0% weight component should not contribute to heatmap cells (Exam category should be empty/None)
        exam_cell = next(cell for cell in m['heatmap_cells'] if cell['category'] == 'Exam')
        self.assertIsNone(exam_cell['val'])

        cw_cell = next(cell for cell in m['heatmap_cells'] if cell['category'] == 'Individual CW')
        self.assertIsNotNone(cw_cell['val'])

    def test_pure_pass_fail_module_analytics(self):
        """Verify that a pure pass/fail module with 0% assessments passes confirmation and dashboard rendering."""
        session = self.client.session
        session["analytics_uploaded_modules"] = [
            {
                'filename': 'PF101.xlsx',
                'module_code': 'PF101',
                'module_title': 'Pass Fail Module',
                'detected_level': 4,
                'scores': [0, 0],
                'year': '2025/26',
                'period': 'SEM1',
                'occurrence': 'BNN',
                'components': [
                    {
                        'column': 'PassFail',
                        'weight': 0,
                        'scores': [100, 100],
                        'detected_category': 'Individual CW'
                    }
                ],
                'row_data_summary': [
                    {
                        'component_scores': {'PassFail': 100.0}
                    },
                    {
                        'component_scores': {'PassFail': 100.0}
                    }
                ]
            }
        ]
        session.save()

        # Try to confirm
        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "PF101",
            "title_0": "Pass Fail Module",
            "level_0": "4",
            "comp_weight_0_0": "0",
            "comp_cat_0_0": "Individual CW"
        })
        # If it succeeds, it should redirect to dashboard
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_dashboard"))
        
        # Follow the redirect to verify dashboard rendering doesn't crash
        dashboard_resp = self.client.get(reverse("analytics_dashboard"))
        self.assertEqual(dashboard_resp.status_code, 200)
        
        # Verify that the 0% pass/fail module is removed from stats (modules context list is empty)
        self.assertEqual(len(dashboard_resp.context["modules"]), 0)
        
        # Verify that snapshot download also excludes the pass/fail module
        snapshot_resp = self.client.get(reverse("download_snapshot"))
        self.assertEqual(snapshot_resp.status_code, 200)
        snapshot_data = json.loads(snapshot_resp.content)
        self.assertEqual(len(snapshot_data["modules"]), 0)

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_pdf_mcrf_upload_and_parse(self, mock_pdf_reader):

        """Verify that a PDF MCRF file can be uploaded and parsed successfully using mocked layout text."""
        from unittest.mock import MagicMock
        
        mock_layout_text = (
            "                                                   Faculty of Science and Environment\n"
            "                                                   Module Marks Record Form (MCRF)\n"
            "                                                                       First Sit\n"
            "Module           KB7071 - Wind, Photovoltaic and Hybrid                              Tutor        Dr John Smith\n"
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
        
        url = reverse("analytics_upload")
        # Post the PDF file
        resp = self.client.post(url, {"files": [uploaded_file]})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_confirm"))
        
        # Verify uploaded modules session data
        session = self.client.session
        self.assertIn("analytics_uploaded_modules", session)
        uploaded = session["analytics_uploaded_modules"]
        self.assertEqual(len(uploaded), 1)
        
        m = uploaded[0]
        self.assertEqual(m["module_code"], "KB7071")
        self.assertEqual(m["module_title"], "Wind, Photovoltaic and Hybrid Renewable Energy Systems")
        self.assertEqual(m["year"], "2025/26")
        self.assertEqual(m["period"], "SEM1")
        self.assertEqual(m["detected_level"], 7)
        self.assertEqual(m["detected_credits"], 20)
        
        # Verify components
        self.assertEqual(len(m["components"]), 2)
        self.assertEqual(m["components"][0]["column"], "001 - 30% - Mark")
        self.assertEqual(m["components"][0]["weight"], 30)
        self.assertEqual(m["components"][1]["column"], "002 - 70% - Mark")
        self.assertEqual(m["components"][1]["weight"], 70)

    def test_generic_marking_sheet_detection(self):
        """Verify that generic marking sheets with headers like 'CW1' and 'Exam' are successfully auto-detected."""
        # Create an Excel workbook in memory with generic headers
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Student ID", "Student Name", "CW1", "CW1 Grade", "Exam", "Overall Total"])
        ws.append(["w12345678", "Alice Smith", 75, "A", 85, 80])
        ws.append(["12345679/2", "Bob Jones", 45, "C", 55, 50])
        
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        
        uploaded_file = SimpleUploadedFile(
            "generic_marks.xlsx",
            buf.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        url = reverse("analytics_upload")
        resp = self.client.post(url, {"files": [uploaded_file]})
        self.assertEqual(resp.status_code, 302)
        
        # Verify component detection
        session = self.client.session
        uploaded = session["analytics_uploaded_modules"][0]
        components = uploaded["components"]
        
        # 'CW1' and 'Exam' should be components, 'CW1 Grade' and 'Overall Total' should be excluded
        detected_columns = [comp["column"] for comp in components]
        self.assertIn("CW1", detected_columns)
        self.assertIn("Exam", detected_columns)
        self.assertNotIn("CW1 Grade", detected_columns)
        self.assertNotIn("Overall Total", detected_columns)
        self.assertEqual(len(detected_columns), 2)

    def test_analytics_confirm_custom_weights_success(self):
        """Verify that confirmation page successfully saves custom weights for non-MCRF modules and recalculates student scores/stats."""
        session = self.client.session
        session["analytics_uploaded_modules"] = [
            {
                'filename': 'generic_module.xlsx',
                'module_code': 'COMP5001',
                'module_title': 'Generic Programming',
                'is_mcrf': False,
                'detected_level': 5,
                'scores': [60, 40],
                'year': '2025/26',
                'period': 'SEM1',
                'occurrence': 'BNN',
                'components': [
                    {
                        'column': 'CW1',
                        'weight': 50,
                        'scores': [80, 20],
                        'detected_category': 'Individual CW'
                    },
                    {
                        'column': 'CW2',
                        'weight': 50,
                        'scores': [40, 60],
                        'detected_category': 'Individual CW'
                    }
                ],
                'row_data_summary': [
                    {
                        'component_scores': {'CW1': 80.0, 'CW2': 40.0}
                    },
                    {
                        'component_scores': {'CW1': 20.0, 'CW2': 60.0}
                    }
                ]
            }
        ]
        session.save()

        # Submit custom weights: CW1 = 30%, CW2 = 70%
        # New expected student 1 score: 80 * 0.3 + 40 * 0.7 = 24 + 28 = 52.0% -> rounded 52
        # New expected student 2 score: 20 * 0.3 + 60 * 0.7 = 6 + 42 = 48.0% -> rounded 48
        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "COMP5001",
            "title_0": "Generic Programming",
            "level_0": "5",
            "comp_weight_0_0": "30",
            "comp_cat_0_0": "Individual CW",
            "comp_weight_0_1": "70",
            "comp_cat_0_1": "Individual CW"
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_dashboard"))

        confirmed = self.client.session["analytics_confirmed_data"]
        self.assertEqual(confirmed["modules"][0]["components"][0]["weight"], 30)
        self.assertEqual(confirmed["modules"][0]["components"][1]["weight"], 70)
        self.assertEqual(confirmed["modules"][0]["mean"], 50.0) # (52 + 48) / 2 = 50.0

    def test_analytics_confirm_custom_weights_validation_error(self):
        """Verify that confirmation page shows error and returns 200 if weights do not sum to 100%."""
        session = self.client.session
        session["analytics_uploaded_modules"] = [
            {
                'filename': 'generic_module.xlsx',
                'module_code': 'COMP5001',
                'module_title': 'Generic Programming',
                'is_mcrf': False,
                'detected_level': 5,
                'scores': [60, 40],
                'year': '2025/26',
                'period': 'SEM1',
                'occurrence': 'BNN',
                'components': [
                    {
                        'column': 'CW1',
                        'weight': 50,
                        'scores': [80, 20],
                        'detected_category': 'Individual CW'
                    },
                    {
                        'column': 'CW2',
                        'weight': 50,
                        'scores': [40, 60],
                        'detected_category': 'Individual CW'
                    }
                ],
                'row_data_summary': [
                    {
                        'component_scores': {'CW1': 80.0, 'CW2': 40.0}
                    }
                ]
            }
        ]
        session.save()

        # Submit invalid weights: CW1 = 40%, CW2 = 50% (total = 90%)
        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "COMP5001",
            "title_0": "Generic Programming",
            "level_0": "5",
            "comp_weight_0_0": "40",
            "comp_cat_0_0": "Individual CW",
            "comp_weight_0_1": "50",
            "comp_cat_0_1": "Individual CW"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Total component weight for module", resp.context["error"])
        
        # Verify weight is updated/preserved in the session
        uploaded = self.client.session["analytics_uploaded_modules"]
        self.assertEqual(uploaded[0]["components"][0]["weight"], 40)
        self.assertEqual(uploaded[0]["components"][1]["weight"], 50)

    def test_confirm_view_merges_duplicate_module_codes(self):
        """Verify that confirmation page merges modules with the same confirmed module code and computes combined cohort statistics correctly."""
        session = self.client.session
        session["analytics_uploaded_modules"] = [
            {
                'filename': 'COMP7001_BNN.xlsx',
                'module_code': 'COMP7001',
                'module_title': 'Advanced Software Engineering',
                'is_mcrf': True,
                'detected_level': 7,
                'detected_credits': 20,
                'scores': [60, 80],
                'year': '2025/26',
                'period': 'SEM1',
                'occurrence': 'BNN',
                'components': [
                    {
                        'column': 'CW1 (100%)',
                        'weight': 100,
                        'scores': [60, 80],
                        'detected_category': 'Individual CW'
                    }
                ],
                'row_data_summary': [
                    {'component_scores': {'CW1 (100%)': 60.0}},
                    {'component_scores': {'CW1 (100%)': 80.0}}
                ]
            },
            {
                'filename': 'COMP7001_FNN.xlsx',
                'module_code': 'COMP7001',
                'module_title': 'Advanced Software Engineering',
                'is_mcrf': True,
                'detected_level': 7,
                'detected_credits': 20,
                'scores': [40, 50],
                'year': '2025/26',
                'period': 'SEM2',
                'occurrence': 'FNN',
                'components': [
                    {
                        'column': 'CW1 (100%)',
                        'weight': 100,
                        'scores': [40, 50],
                        'detected_category': 'Individual CW'
                    }
                ],
                'row_data_summary': [
                    {'component_scores': {'CW1 (100%)': 40.0}},
                    {'component_scores': {'CW1 (100%)': 50.0}}
                ]
            }
        ]
        session.save()

        # Both occurrences are confirmed with the module code 'COMP7001'
        url = reverse("analytics_confirm")
        resp = self.client.post(url, {
            "programme_name": "MSc Computer Science",
            "academic_year": "2025/26",
            "code_0": "COMP7001",
            "title_0": "Advanced Software Engineering",
            "level_0": "7",
            "credits_0": "20",
            "comp_weight_0_0": "100",
            "comp_cat_0_0": "Individual CW",
            "code_1": "COMP7001",
            "title_1": "Advanced Software Engineering",
            "level_1": "7",
            "credits_1": "20",
            "comp_weight_1_0": "100",
            "comp_cat_1_0": "Individual CW"
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("analytics_dashboard"))

        # Verify combined results in the session
        confirmed = self.client.session["analytics_confirmed_data"]
        modules = confirmed["modules"]
        
        # There should be exactly 1 merged module for 'COMP7001'
        self.assertEqual(len(modules), 1)
        m = modules[0]
        self.assertEqual(m["module_code"], "COMP7001")
        self.assertEqual(m["level"], 7)
        self.assertEqual(m["cohort_size"], 4)
        
        # Combined scores should be: [60, 80, 40, 50]
        self.assertEqual(sorted(m["scores"]), [40, 50, 60, 80])
        
        # Recalculated stats check:
        # Mean = (40+50+60+80)/4 = 230/4 = 57.5%
        # Median = (50+60)/2 = 55.0%
        # Fail threshold for level 7 is 50%. Fails: [40] -> 1/4 = 25% fail rate
        # 1st-class threshold is >= 70%. 1st: [80] -> 1/4 = 25% 1st class rate
        self.assertAlmostEqual(m["mean"], 57.5)
        self.assertAlmostEqual(m["median"], 55.0)
        self.assertAlmostEqual(m["pct_fail"], 25.0)
        self.assertAlmostEqual(m["pct_1st"], 25.0)

        # Combined components check
        self.assertEqual(len(m["components"]), 1)
        comp = m["components"][0]
        self.assertEqual(comp["column"], "CW1 (100%)")
        self.assertEqual(sorted(comp["scores"]), [40, 50, 60, 80])
        
        # Filename should list both source filenames
        self.assertIn("COMP7001_BNN.xlsx", m["filename"])
        self.assertIn("COMP7001_FNN.xlsx", m["filename"])

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_pdf_mcrf_confirm_and_merge(self, mock_pdf_reader):
        """Verify that two uploaded PDF files for the same module are successfully merged and their stats recalculated."""
        from unittest.mock import MagicMock
        
        mock_layout_bnn = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7071 - Wind Energy Systems\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Individual report (2,500 words or equivalent)                                                                                           30%\n"
            "002           Individual report (3,500 words or equivalent)                                                                                           70%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            "11111111/1    SMITH, ALICE                              BNN       SEM1         60      P      80      P      74      P\n"
        )
        
        mock_layout_fnn = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7071 - Wind Energy Systems\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       FNN: January start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Individual report (2,500 words or equivalent)                                                                                           30%\n"
            "002           Individual report (3,500 words or equivalent)                                                                                           70%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            "22222222/1    BROWN, ROBERT                             FNN       SEM1         40      P      50      P      47      P\n"
        )
        
        # We want PdfReader call 1 to return BNN layout, call 2 to return FNN layout
        mock_reader_bnn = MagicMock()
        mock_page_bnn = MagicMock()
        mock_page_bnn.extract_text.return_value = mock_layout_bnn
        mock_reader_bnn.pages = [mock_page_bnn]
        
        mock_reader_fnn = MagicMock()
        mock_page_fnn = MagicMock()
        mock_page_fnn.extract_text.return_value = mock_layout_fnn
        mock_reader_fnn.pages = [mock_page_fnn]
        
        mock_pdf_reader.side_effect = [mock_reader_bnn, mock_reader_fnn]
        
        uploaded_bnn = SimpleUploadedFile(
            "KB7071_BNN.pdf",
            b"%PDF-1.4\n%mocked bnn pdf",
            content_type="application/pdf"
        )
        uploaded_fnn = SimpleUploadedFile(
            "KB7071_FNN.pdf",
            b"%PDF-1.4\n%mocked fnn pdf",
            content_type="application/pdf"
        )
        
        # 1. Upload both PDFs
        url_upload = reverse("analytics_upload")
        resp_upload = self.client.post(url_upload, {"files": [uploaded_bnn, uploaded_fnn]})
        self.assertEqual(resp_upload.status_code, 302)
        self.assertEqual(resp_upload.url, reverse("analytics_confirm"))
        
        # 2. Confirm both mapped to 'KB7071'
        url_confirm = reverse("analytics_confirm")
        resp_confirm = self.client.post(url_confirm, {
            "programme_name": "MSc Computer Science",
            "academic_year": "2025/26",
            "code_0": "KB7071",
            "title_0": "Wind Energy Systems",
            "level_0": "7",
            "credits_0": "20",
            "comp_weight_0_0": "30",
            "comp_cat_0_0": "Individual CW",
            "comp_weight_0_1": "70",
            "comp_cat_0_1": "Individual CW",
            "code_1": "KB7071",
            "title_1": "Wind Energy Systems",
            "level_1": "7",
            "credits_1": "20",
            "comp_weight_1_0": "30",
            "comp_cat_1_0": "Individual CW",
            "comp_weight_1_1": "70",
            "comp_cat_1_1": "Individual CW",
        })
        self.assertEqual(resp_confirm.status_code, 302)
        self.assertEqual(resp_confirm.url, reverse("analytics_dashboard"))
        
        # 3. Check combined session data
        confirmed = self.client.session["analytics_confirmed_data"]
        modules = confirmed["modules"]
        self.assertEqual(len(modules), 1)
        m = modules[0]
        self.assertEqual(m["module_code"], "KB7071")
        self.assertEqual(m["cohort_size"], 2)
        
        # Recalculated marks:
        # BNN student: 60 * 0.3 + 80 * 0.7 = 18 + 56 = 74
        # FNN student: 40 * 0.3 + 50 * 0.7 = 12 + 35 = 47
        self.assertEqual(sorted(m["scores"]), [47, 74])
        self.assertAlmostEqual(m["mean"], 60.5)
        self.assertAlmostEqual(m["pct_fail"], 50.0) # 47 is < 50 for level 7
        self.assertAlmostEqual(m["pct_1st"], 50.0) # 74 is >= 70
        
        # Components should be combined
        self.assertEqual(len(m["components"]), 2)
        comp_001 = next(c for c in m["components"] if "001" in c["column"])
        self.assertEqual(sorted(comp_001["scores"]), [40, 60])
        comp_002 = next(c for c in m["components"] if "002" in c["column"])
        self.assertEqual(sorted(comp_002["scores"]), [50, 80])

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_pdf_mcrf_multipage_parsing(self, mock_pdf_reader):
        """Verify that a multi-page PDF does not parse duplicate component columns and maps student marks correctly."""
        from unittest.mock import MagicMock
        
        mock_layout_page1 = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7071 - Wind Energy Systems\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Individual report (2,500 words or equivalent)                                                                                           30%\n"
            "002           Individual report (3,500 words or equivalent)                                                                                           70%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            "11111111/1    SMITH, ALICE                              BNN       SEM1         60      P      80      P      74      P\n"
        )
        
        mock_layout_page2 = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7071 - Wind Energy Systems\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Individual report (2,500 words or equivalent)                                                                                           30%\n"
            "002           Individual report (3,500 words or equivalent)                                                                                           70%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            "22222222/1    BROWN, ROBERT                             BNN       SEM1         40      P      50      P      47      P\n"
        )
        
        mock_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = mock_layout_page1
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = mock_layout_page2
        
        mock_reader.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader
        
        uploaded_file = SimpleUploadedFile(
            "KB7071_multipage.pdf",
            b"%PDF-1.4\n%mocked multipage pdf",
            content_type="application/pdf"
        )
        
        url_upload = reverse("analytics_upload")
        resp_upload = self.client.post(url_upload, {"files": [uploaded_file]})
        self.assertEqual(resp_upload.status_code, 302)
        
        # Verify components in session uploaded modules list has NO duplicates (only 2 components)
        uploaded = self.client.session["analytics_uploaded_modules"]
        self.assertEqual(len(uploaded), 1)
        m = uploaded[0]
        self.assertEqual(len(m["components"]), 2)
        self.assertEqual(m["components"][0]["column"], "001 - 30% - Mark")
        self.assertEqual(m["components"][1]["column"], "002 - 70% - Mark")

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_pdf_files_parse_and_merge_mocked(self, mock_pdf_reader):
        """Verify that mocked BNN and FNN PDF files parse and merge correctly."""
        from unittest.mock import MagicMock
        
        # Construct BNN layout (10 students)
        bnn_student_lines = []
        for i in range(10):
            stud_id = f"23{i:06d}/1"
            name = f"STUDENT_BNN, NAME {i}"
            cw2 = 60 + i
            cw3 = 70 + i
            overall = int(round(cw2 * 0.8 + cw3 * 0.2))
            
            # Col Targets: [75, 81, 89, 95, 103, 109, 117, 124]
            # prefix: 14 + 41 + 10 + 10 = 75
            bnn_student_lines.append(
                f"{stud_id:<14}{name:<41}{'BNN':<10}{'SEM1':<10}      GP      {cw2:<6}P       {cw3:<6}P       {overall:<7}P"
            )
            
        mock_layout_bnn = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7069 - Research Project\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "CW1           Component 1                                                                                                                             0%\n"
            "CW2           Component 2                                                                                                                            80%\n"
            "CW3           Component 3                                                                                                                            20%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade   Mark   Grade\n"
            + "\n".join(bnn_student_lines)
        )
        
        # Construct FNN layout (16 students)
        fnn_student_lines = []
        for i in range(16):
            stud_id = f"24{i:06d}/1"
            name = f"STUDENT_FNN, NAME {i}"
            cw2 = 50 + i
            cw3 = 60 + i
            overall = int(round(cw2 * 0.8 + cw3 * 0.2))
            
            # prefix: 14 + 41 + 10 + 10 = 75
            fnn_student_lines.append(
                f"{stud_id:<14}{name:<41}{'FNN':<10}{'SEM1':<10}      GP      {cw2:<6}P       {cw3:<6}P       {overall:<7}P"
            )
            
        mock_layout_fnn = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB7069 - Research Project\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       FNN: January start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "CW1           Component 1                                                                                                                             0%\n"
            "CW2           Component 2                                                                                                                            80%\n"
            "CW3           Component 3                                                                                                                            20%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade   Mark   Grade\n"
            + "\n".join(fnn_student_lines)
        )
        
        mock_reader_bnn = MagicMock()
        mock_page_bnn = MagicMock()
        mock_page_bnn.extract_text.return_value = mock_layout_bnn
        mock_reader_bnn.pages = [mock_page_bnn]
        
        mock_reader_fnn = MagicMock()
        mock_page_fnn = MagicMock()
        mock_page_fnn.extract_text.return_value = mock_layout_fnn
        mock_reader_fnn.pages = [mock_page_fnn]
        
        mock_pdf_reader.side_effect = [mock_reader_bnn, mock_reader_fnn]
        
        uploaded_bnn = SimpleUploadedFile("MCRF - Academics-BNN KB7069.pdf", b"%PDF-1.4\n%mocked bnn", content_type="application/pdf")
        uploaded_fnn = SimpleUploadedFile("MCRF - Academics-FNN KB7069.pdf", b"%PDF-1.4\n%mocked fnn", content_type="application/pdf")
            
        url_upload = reverse("analytics_upload")
        resp_upload = self.client.post(url_upload, {"files": [uploaded_bnn, uploaded_fnn]})
        self.assertEqual(resp_upload.status_code, 302)
        
        # Verify uploaded modules session data
        session = self.client.session
        uploaded = session["analytics_uploaded_modules"]
        self.assertEqual(len(uploaded), 2)
        
        # Check BNN KB7069 details
        bnn_mod = next(m for m in uploaded if "BNN" in m["filename"])
        self.assertEqual(bnn_mod["module_code"], "KB7069")
        self.assertEqual(len(bnn_mod["scores"]), 10)
        
        # Post confirmation mapping
        url_confirm = reverse("analytics_confirm")
        resp_confirm = self.client.post(url_confirm, {
            "programme_name": "MSc Computer Science",
            "academic_year": "2025/26",
            "code_0": "KB7069",
            "title_0": "Research Project",
            "level_0": "7",
            "credits_0": "60",
            "comp_weight_0_0": "0",
            "comp_cat_0_0": "Individual CW",
            "comp_weight_0_1": "80",
            "comp_cat_0_1": "Individual CW",
            "comp_weight_0_2": "20",
            "comp_cat_0_2": "Presentation",
            "code_1": "KB7069",
            "title_1": "Research Project",
            "level_1": "7",
            "credits_1": "60",
            "comp_weight_1_0": "0",
            "comp_cat_1_0": "Individual CW",
            "comp_weight_1_1": "80",
            "comp_cat_1_1": "Individual CW",
            "comp_weight_1_2": "20",
            "comp_cat_1_2": "Presentation"
        })
        self.assertEqual(resp_confirm.status_code, 302)
        
        # Check combined results
        confirmed = self.client.session["analytics_confirmed_data"]
        modules = confirmed["modules"]
        self.assertEqual(len(modules), 1)
        m = modules[0]
        self.assertEqual(m["module_code"], "KB7069")
        self.assertEqual(m["cohort_size"], 26) # 10 BNN + 16 FNN = 26 total students

    @patch('core.mcrf_parser.pypdf.PdfReader')
    def test_kb6055_pdf_parse_and_stats_mocked(self, mock_pdf_reader):
        """Verify that mocked KB6055 MCRF PDF parses correctly and calculates correct fail rate/statistics."""
        from unittest.mock import MagicMock
        
        # Generate 98 mock student lines with varying spacing shifts
        student_lines = []
        for i in range(98):
            stud_id = f"22{i:06d}/1"
            name = f"STUDENT, NAME {i}"
            # Fail threshold is 40% for level 6.
            # Make 25 fail (overall < 40) and 73 pass (overall >= 40)
            if i < 25:
                cw1 = 30
                exam = 35
                overall = 34
                grade = "R"
            else:
                cw1 = 60
                exam = 65
                overall = 64
                grade = "P"
                
            # Col Targets: [75, 81, 89, 95, 103, 109]
            # Vary spacing slightly to test dynamic shift optimizer:
            if i % 3 == 0:
                # Normal spacing (prefix length = 75)
                student_lines.append(
                    f"{stud_id:<14}{name:<41}{'BNN':<10}{'SEM1':<10}{cw1:<6}{grade:<8}{exam:<6}{grade:<8}{overall:<6}{grade}"
                )
            elif i % 3 == 1:
                # Shifted left by 4 spaces (prefix length = 71)
                student_lines.append(
                    f"{stud_id:<14}{name:<41}{'BNN':<10}{'SEM1':<6}{cw1:<6}{grade:<8}{exam:<6}{grade:<8}{overall:<6}{grade}"
                )
            else:
                # Shifted right by 4 spaces (prefix length = 79)
                student_lines.append(
                    f"{stud_id:<14}{name:<41}{'BNN':<10}{'SEM1':<14}{cw1:<6}{grade:<8}{exam:<6}{grade:<8}{overall:<6}{grade}"
                )
                
        mock_layout_kb6055 = (
            "Faculty of Science and Environment\n"
            "Module Marks Record Form (MCRF)\n"
            "Module           KB6055 - Some Title\n"
            "Year             2025/6\n"
            "Period           SEM1\n"
            "Occurrence       BNN: September start - Newcastle upon Tyne\n"
            "Component                                                                                                                                       Weighting\n"
            "001           Component 1                                                                                                                             30%\n"
            "002           Component 2                                                                                                                             70%\n"
            "Student ID                                              Occ       Period      Mark  Grade   Mark   Grade   Mark   Grade\n"
            + "\n".join(student_lines)
        )
        
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = mock_layout_kb6055
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        uploaded_kb6055 = SimpleUploadedFile("KB6055 MCRF.pdf", b"%PDF-1.4\n%mocked kb6055", content_type="application/pdf")
            
        url_upload = reverse("analytics_upload")
        resp_upload = self.client.post(url_upload, {"files": [uploaded_kb6055]})
        session = self.client.session
        uploaded = session["analytics_uploaded_modules"]
        self.assertEqual(len(uploaded), 1)
        
        kb_mod = uploaded[0]
        self.assertEqual(kb_mod["module_code"], "KB6055")
        self.assertEqual(len(kb_mod["scores"]), 98)
        
        # Post confirmation mapping
        url_confirm = reverse("analytics_confirm")
        resp_confirm = self.client.post(url_confirm, {
            "programme_name": "BEng Computer Science",
            "academic_year": "2025/26",
            "code_0": "KB6055",
            "title_0": "Some Title",
            "level_0": "6",
            "credits_0": "20",
            "comp_weight_0_0": "30",
            "comp_cat_0_0": "Individual CW",
            "comp_weight_0_1": "70",
            "comp_cat_0_1": "Exam",
        })
        self.assertEqual(resp_confirm.status_code, 302)
        
        # Check results in dashboard session data
        confirmed = self.client.session["analytics_confirmed_data"]
        modules = confirmed["modules"]
        self.assertEqual(len(modules), 1)
        m = modules[0]
        self.assertEqual(m["module_code"], "KB6055")
        self.assertEqual(m["cohort_size"], 98)
        # Fail threshold is 40% for level 6.
        # Verified fail count is 25 out of 98.
        # Fail rate: 25 / 98 * 100 = 25.51%
        self.assertAlmostEqual(m["pct_fail"], 25.510204, places=2)



