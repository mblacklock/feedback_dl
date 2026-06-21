import io
import json
import openpyxl
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from longitudinal_analytics.views import (
    infer_module_level,
    auto_detect_year_from_filename,
    pearson_correlation,
    normalize_year,
    get_level_4_equivalent_year,
    filter_students_by_cohort_year,
    extract_occurrence_code,
    filter_students_by_occurrence
)


class LongitudinalAnalyticsTests(TestCase):
    def setUp(self):
        # Create a dummy MCRF Workbook in memory
        self.wb = openpyxl.Workbook()
        ws = self.wb.active
        ws.append(["Module Marks Record Form (MCRF)"])
        ws.append(["COMP4001 - Programming Fundamentals"])
        ws.append(["", "", "CW1 (50%)", "CW1 (50%)", "EX1 (50%)", "EX1 (50%)"])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345", "Alice Smith", 80, "A", 90, "A"])
        ws.append(["w12346", "Bob Jones", 40, "D", 50, "C"])
        ws.append(["w12347", "Charlie Brown", 30, "F", 20, "F"])

        self.excel_bytes = io.BytesIO()
        self.wb.save(self.excel_bytes)
        self.excel_bytes.seek(0)

        # Pre-populated confirmed cohort data for testing dashboard views
        self.sample_confirmed_data = [
            {
                'filename': 'COMP4001.xlsx',
                'module_code': 'COMP4001',
                'module_title': 'Programming Fundamentals',
                'is_mcrf': True,
                'level': 4,
                'credits': 20,
                'year': '2022/23',
                'components': [
                    {'column': 'CW1 (50%)', 'weight': 50, 'category': 'Individual CW'},
                    {'column': 'EX1 (50%)', 'weight': 50, 'category': 'Exam'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'CW1 (50%)': 80.0, 'EX1 (50%)': 90.0}, 'overall_mark': 85},
                    {'student_id': 'w12346', 'component_scores': {'CW1 (50%)': 40.0, 'EX1 (50%)': 50.0}, 'overall_mark': 45},
                    {'student_id': 'w12347', 'component_scores': {'CW1 (50%)': 30.0, 'EX1 (50%)': 20.0}, 'overall_mark': 25}
                ]
            },
            {
                'filename': 'COMP4002.xlsx',
                'module_code': 'COMP4002',
                'module_title': 'Pass Fail Module',
                'is_mcrf': True,
                'level': 4,
                'credits': 20,
                'year': '2022/23',
                'components': [
                    {'column': 'P1 (0%)', 'weight': 0, 'category': 'Individual CW'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'P1 (0%)': 100.0}, 'overall_mark': 0},
                    {'student_id': 'w12346', 'component_scores': {'P1 (0%)': 100.0}, 'overall_mark': 0},
                    {'student_id': 'w12347', 'component_scores': {'P1 (0%)': 0.0}, 'overall_mark': 0}
                ]
            },
            {
                'filename': 'COMP5002.xlsx',
                'module_code': 'COMP5002',
                'module_title': 'Software Engineering',
                'is_mcrf': True,
                'level': 5,
                'credits': 20,
                'year': '2023/24',
                'components': [
                    {'column': 'CW1 (100%)', 'weight': 100, 'category': 'Individual CW'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'CW1 (100%)': 70.0}, 'overall_mark': 70},
                    {'student_id': 'w12346', 'component_scores': {'CW1 (100%)': 40.0}, 'overall_mark': 40},
                    {'student_id': 'w12347', 'component_scores': {'CW1 (100%)': 28.0}, 'overall_mark': 28}
                ]
            },
            {
                'filename': 'COMP6003.xlsx',
                'module_code': 'COMP6003',
                'module_title': 'Advanced Development',
                'is_mcrf': True,
                'level': 6,
                'credits': 20,
                'year': '2024/25',
                'components': [
                    {'column': 'EX1 (100%)', 'weight': 100, 'category': 'Exam'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'EX1 (100%)': 75.0}, 'overall_mark': 75},
                    {'student_id': 'w12346', 'component_scores': {'EX1 (100%)': 42.0}, 'overall_mark': 42}
                ]
            }
        ]

    def test_infer_module_level(self):
        """Verify module levels are correctly parsed from codes."""
        self.assertEqual(infer_module_level('COMP3000'), 3)
        self.assertEqual(infer_module_level('COMP4001'), 4)
        self.assertEqual(infer_module_level('COMP5002'), 5)
        self.assertEqual(infer_module_level('COMP6003'), 6)
        self.assertEqual(infer_module_level('COMP7004'), 7)
        self.assertEqual(infer_module_level('INVALID'), 4)

    def test_auto_detect_year_from_filename(self):
        """Verify academic years are parsed correctly from filenames."""
        self.assertEqual(auto_detect_year_from_filename('COMP4001_2022.xlsx'), '2022/23')
        self.assertEqual(auto_detect_year_from_filename('COMP5002-2023-24.xlsx'), '2023/24')
        self.assertEqual(auto_detect_year_from_filename('COMP6003_24_25.pdf'), '2024/25')
        self.assertEqual(auto_detect_year_from_filename('COMP6003.xlsx'), '')

    def test_normalize_year(self):
        """Verify normalization of academic year strings to YYYY/YY format."""
        self.assertEqual(normalize_year('2025/6'), '2025/26')
        self.assertEqual(normalize_year('2025/26'), '2025/26')
        self.assertEqual(normalize_year('2025-26'), '2025/26')
        self.assertEqual(normalize_year('2025_26'), '2025/26')
        self.assertEqual(normalize_year('2025'), '2025/26')
        self.assertEqual(normalize_year('  2023 / 4 '), '2023/24')
        self.assertEqual(normalize_year('invalid_format'), 'invalid_format')
        self.assertEqual(normalize_year(''), '')

    def test_pearson_correlation(self):
        """Verify pearson correlation calculation returns expected coefficients."""
        x = [50, 60, 70, 80]
        y = [50, 60, 70, 80]
        # Perfect positive correlation
        self.assertAlmostEqual(pearson_correlation(x, y), 1.0)

        y2 = [80, 70, 60, 50]
        # Perfect negative correlation
        self.assertAlmostEqual(pearson_correlation(x, y2), -1.0)

        # Fewer than 3 elements returns None
        self.assertIsNone(pearson_correlation([50, 60], [50, 60]))

    def test_upload_view_get(self):
        """Verify upload view loads correctly via GET."""
        response = self.client.get(reverse('longitudinal_upload'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'longitudinal_analytics/upload.html')

    def test_upload_view_post_valid(self):
        """Verify uploading a valid MCRF workbook redirects to mapping confirmation."""
        uploaded_file = SimpleUploadedFile(
            "COMP4001_2022.xlsx",
            self.excel_bytes.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post(reverse('longitudinal_upload'), {'files': [uploaded_file]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('longitudinal_confirm')))

        # Verify parsed data stored in session
        session_modules = self.client.session.get('longitudinal_uploaded_modules')
        self.assertIsNotNone(session_modules)
        self.assertEqual(len(session_modules), 1)
        self.assertEqual(session_modules[0]['module_code'], 'COMP4001')
        self.assertEqual(session_modules[0]['detected_year'], '2022/23')
        self.assertEqual(len(session_modules[0]['raw_rows']), 3)

    def test_confirm_view_post_valid(self):
        """Verify confirmation post mapping redirects to dashboard."""
        session = self.client.session
        session['longitudinal_uploaded_modules'] = [
            {
                'filename': 'COMP4001_2022.xlsx',
                'module_code': 'COMP4001',
                'module_title': 'Programming Fundamentals',
                'is_mcrf': True,
                'detected_level': 4,
                'detected_credits': 20,
                'detected_year': '2022/23',
                'components': [
                    {'column': 'CW1 (50%)', 'weight': 50, 'detected_category': 'Individual CW'},
                    {'column': 'EX1 (50%)', 'weight': 50, 'detected_category': 'Exam'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'CW1 (50%)': 80.0, 'EX1 (50%)': 90.0}, 'overall_mark': 85}
                ]
            }
        ]
        session.save()

        # Submit confirmation mapping
        post_data = {
            'code_0': 'COMP4001',
            'title_0': 'Programming Fundamentals',
            'year_0': '2022/23',
            'level_0': '4',
            'credits_0': '20',
            'comp_weight_0_0': '50',
            'comp_cat_0_0': 'Individual CW',
            'comp_weight_0_1': '50',
            'comp_cat_0_1': 'Exam'
        }
        response = self.client.post(reverse('longitudinal_confirm'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('longitudinal_dashboard')))

        # Check session confirmed data exists
        confirmed_data = self.client.session.get('longitudinal_confirmed_data')
        self.assertIsNotNone(confirmed_data)
        self.assertEqual(confirmed_data[0]['year'], '2022/23')
        self.assertEqual(confirmed_data[0]['level'], 4)

    def test_confirm_view_validation_error(self):
        """Verify confirmation post fails when custom component weights do not sum to 100%."""
        session = self.client.session
        session['longitudinal_uploaded_modules'] = [
            {
                'filename': 'COMP4001.xlsx',
                'module_code': 'COMP4001',
                'module_title': 'Programming Fundamentals',
                'is_mcrf': False, # trigger weighting editing
                'detected_level': 4,
                'detected_credits': 20,
                'detected_year': '2022/23',
                'components': [
                    {'column': 'CW1', 'weight': 50, 'detected_category': 'Individual CW'},
                    {'column': 'EX1', 'weight': 50, 'detected_category': 'Exam'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'CW1': 80.0, 'EX1': 90.0}, 'overall_mark': 85}
                ]
            }
        ]
        session.save()

        # Submit invalid weights summing to 90%
        post_data = {
            'code_0': 'COMP4001',
            'title_0': 'Programming Fundamentals',
            'year_0': '2022/23',
            'level_0': '4',
            'credits_0': '20',
            'comp_weight_0_0': '40',
            'comp_cat_0_0': 'Individual CW',
            'comp_weight_0_1': '50',
            'comp_cat_0_1': 'Exam'
        }
        response = self.client.post(reverse('longitudinal_confirm'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must sum to exactly 100% or 0%")

    def test_confirm_view_validation_allows_zero_weight(self):
        """Verify confirmation post succeeds when component weights sum to 0% (pass/fail module)."""
        session = self.client.session
        session['longitudinal_uploaded_modules'] = [
            {
                'filename': 'COMP4002.xlsx',
                'module_code': 'COMP4002',
                'module_title': 'Pass Fail Module',
                'is_mcrf': False,
                'detected_level': 4,
                'detected_credits': 20,
                'detected_year': '2022/23',
                'components': [
                    {'column': 'CW1', 'weight': 50, 'detected_category': 'Individual CW'},
                    {'column': 'EX1', 'weight': 50, 'detected_category': 'Exam'}
                ],
                'raw_rows': [
                    {'student_id': 'w12345', 'component_scores': {'CW1': 80.0, 'EX1': 90.0}, 'overall_mark': 85}
                ]
            }
        ]
        session.save()

        # Submit weights summing to 0%
        post_data = {
            'code_0': 'COMP4002',
            'title_0': 'Pass Fail Module',
            'year_0': '2022/23',
            'level_0': '4',
            'credits_0': '20',
            'comp_weight_0_0': '0',
            'comp_cat_0_0': 'Individual CW',
            'comp_weight_0_1': '0',
            'comp_cat_0_1': 'Exam'
        }
        response = self.client.post(reverse('longitudinal_confirm'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('longitudinal_dashboard')))

    def test_dashboard_view_and_scatter_api(self):
        """Verify dashboard loaded from confirmed data compiles all analytics aggregates correctly."""
        session = self.client.session
        session['longitudinal_confirmed_data'] = self.sample_confirmed_data
        session.save()

        # Load dashboard
        response = self.client.get(reverse('longitudinal_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'longitudinal_analytics/dashboard.html')

        # Check calculated context variables
        self.assertEqual(response.context['module_codes'], ['COMP4001', 'COMP4002', 'COMP5002', 'COMP6003'])
        
        # Verify that pass/fail module COMP4002 is excluded from Level 4 cohort progression average.
        # Cohort "Entered L4 in 2022/23" progression line is serialized in chart_cohort_lines_json.
        chart_cohort_lines = json.loads(response.context['chart_cohort_lines_json'])
        cohort_line = next(line for line in chart_cohort_lines if "Entered L4 in 2022/23" in line["label"])
        # Levels are [3, 4, 5, 6, 7], Level 4 is index 1.
        # If COMP4002 was not excluded, it would be around 25.8. Since it is excluded, it is 51.7.
        self.assertEqual(cohort_line["data"][1], 51.7)
        
        # Test scatter plot API
        scatter_response = self.client.get(reverse('longitudinal_scatter_data'), {
            'mod1': 'COMP4001',
            'mod2': 'COMP5002'
        })
        self.assertEqual(scatter_response.status_code, 200)
        data = json.loads(scatter_response.content)
        self.assertEqual(data['n'], 3)
        self.assertIsNotNone(data['r'])
        self.assertEqual(len(data['points']), 3)

    def test_dashboard_heatmap_filtering_with_threshold(self):
        """Verify that the dashboard correlation matrix (heatmap) filters out marks below a custom threshold."""
        session = self.client.session
        session['longitudinal_confirmed_data'] = self.sample_confirmed_data
        session.save()

        # Load dashboard with custom threshold of 30%
        response = self.client.get(reverse('longitudinal_dashboard'), {'non_sub_threshold': 30})
        self.assertEqual(response.status_code, 200)

        # Inspect the matrix_data context variable
        # w12347 has COMP4001: 25 and COMP5002: 28. With threshold 30, w12347 is excluded.
        # w12345 (85, 70) and w12346 (45, 40) are both >= 30, so they are included.
        # So the overlap count (n) for COMP4001 vs COMP5002 cell should be 2.
        matrix_data = response.context['matrix_data']
        
        # Find cell for COMP4001 vs COMP5002
        row_comp4001 = next(row for row in matrix_data if row['module_code'] == 'COMP4001')
        cell_comp5002 = next(cell for cell in row_comp4001['cells'] if cell['mod2'] == 'COMP5002')
        
        self.assertEqual(cell_comp5002['n'], 2)

    def test_student_cohort_filtering(self):
        """Verify Level 4 equivalent year calculation and student filtering by cohort."""
        # 1. Student entering L3 in 2021/22 (should be in 2022/23 cohort)
        student_l3 = {
            'COMP3001': {'level': 3, 'year': '2021/22', 'mark': 70}
        }
        self.assertEqual(get_level_4_equivalent_year(student_l3), '2022/23')

        # 2. Student entering L4 in 2022/23 (should be in 2022/23 cohort)
        student_l4 = {
            'COMP4001': {'level': 4, 'year': '2022/23', 'mark': 75}
        }
        self.assertEqual(get_level_4_equivalent_year(student_l4), '2022/23')

        # 3. Direct entrant at L5 in 2023/24 (should be in 2022/23 cohort)
        student_l5 = {
            'COMP5001': {'level': 5, 'year': '2023/24', 'mark': 80}
        }
        self.assertEqual(get_level_4_equivalent_year(student_l5), '2022/23')

        # 4. Student entering L4 in 2023/24 (should be in 2023/24 cohort)
        student_l4_next = {
            'COMP4001': {'level': 4, 'year': '2023/24', 'mark': 60}
        }
        self.assertEqual(get_level_4_equivalent_year(student_l4_next), '2023/24')

        # Setup students_meta for filtering tests
        students_meta = {
            's_l3': student_l3,
            's_l4': student_l4,
            's_l5': student_l5,
            's_l4_next': student_l4_next
        }

        # Filter for single year '2022/23'
        filtered_2022 = filter_students_by_cohort_year(students_meta, 'single', single_year='2022/23')
        self.assertEqual(filtered_2022, {'s_l3', 's_l4', 's_l5'})

        # Filter for range '2022/23' to '2023/24'
        filtered_range = filter_students_by_cohort_year(students_meta, 'range', start_year='2022/23', end_year='2023/24')
        self.assertEqual(filtered_range, {'s_l3', 's_l4', 's_l5', 's_l4_next'})

    def test_level_7_occurrence_handling(self):
        """Verify occurrence detection, formatting, and filtering logic."""
        # 1. Occurrence detection tests
        self.assertEqual(extract_occurrence_code("BNN: September Start", ""), "BNN")
        self.assertEqual(extract_occurrence_code("", "COMP7001_FNN.xlsx"), "FNN")
        self.assertEqual(extract_occurrence_code("XYZ Start", ""), "XYZ")
        # Ignore common metadata words
        self.assertEqual(extract_occurrence_code("MCRF occurrence L7", ""), "")

        # 2. Filter students by occurrence tests
        students_meta = {
            's1': {
                'COMP7001': {'level': 7, 'year': '2025/26', 'occurrence': 'BNN'}
            },
            's2': {
                'COMP7001': {'level': 7, 'year': '2025/26', 'occurrence': 'FNN'}
            },
            's3': {
                # Undergraduate student - no Level 7 occurrence
                'COMP4001': {'level': 4, 'year': '2022/23', 'occurrence': ''}
            }
        }

        # Filter for 'BNN'
        filtered_bnn = filter_students_by_occurrence(students_meta, 'BNN')
        self.assertEqual(filtered_bnn, {'s1'})

        # Filter for 'FNN'
        filtered_fnn = filter_students_by_occurrence(students_meta, 'FNN')
        self.assertEqual(filtered_fnn, {'s2'})

        # Filter for 'all' or empty
        self.assertEqual(filter_students_by_occurrence(students_meta, 'all'), {'s1', 's2', 's3'})
        self.assertEqual(filter_students_by_occurrence(students_meta, ''), {'s1', 's2', 's3'})

    def test_confirm_view_occurrence_split_and_merge(self):
        """Verify that occurrences are merged or split correctly based on user choice."""
        # 1. Test Split behavior
        session = self.client.session
        session['longitudinal_uploaded_modules'] = [
            {
                'filename': 'COMP7001_BNN.xlsx',
                'module_code': 'COMP7001',
                'module_title': 'Advanced Research Methods',
                'is_mcrf': True,
                'detected_level': 7,
                'detected_credits': 20,
                'detected_year': '2025/26',
                'detected_occurrence': 'BNN',
                'components': [
                    {'column': 'CW1 (100%)', 'weight': 100, 'detected_category': 'Individual CW'}
                ],
                'raw_rows': [
                    {'student_id': 'w99999', 'component_scores': {'CW1 (100%)': 80.0}, 'overall_mark': 80.0}
                ]
            }
        ]
        session.save()

        post_data = {
            'code_0': 'COMP7001',
            'title_0': 'Advanced Research Methods',
            'year_0': '2025/26',
            'level_0': '7',
            'credits_0': '20',
            'comp_weight_0_0': '100',
            'comp_cat_0_0': 'Individual CW',
            'occ_handle_bulk': 'separate'  # split occurrences globally
        }
        response = self.client.post(reverse('longitudinal_confirm'), post_data)
        self.assertEqual(response.status_code, 302)
        confirmed_data = self.client.session.get('longitudinal_confirmed_data')
        self.assertEqual(confirmed_data[0]['module_code'], 'COMP7001-BNN')

        # 2. Test Merge behavior
        post_data['occ_handle_bulk'] = 'merge'  # merge occurrences globally
        response = self.client.post(reverse('longitudinal_confirm'), post_data)
        self.assertEqual(response.status_code, 302)
        confirmed_data = self.client.session.get('longitudinal_confirmed_data')
        self.assertEqual(confirmed_data[0]['module_code'], 'COMP7001')
