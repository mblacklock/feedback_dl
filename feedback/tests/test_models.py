from django.test import TestCase
from django.core.exceptions import ValidationError
from feedback.models import AssessmentTemplate


class AssessmentTemplateModelTests(TestCase):
    def test_can_create_template_with_ordered_categories(self):
        tpl = AssessmentTemplate.objects.create(
            title="KB5031 – FEA Coursework",
            module_code="KB5031",
            assessment_title="Coursework 1",
            categories=[
                {"label": "Introduction", "max": 10},
                {"label": "Method", "max": 20},
                {"label": "Design", "max": 10},
            ],
        )
        self.assertEqual(tpl.title, "KB5031 – FEA Coursework")
        self.assertEqual(tpl.module_code, "KB5031")
        self.assertEqual(
            tpl.categories,
            [
                {"label": "Introduction", "max": 10},
                {"label": "Method", "max": 20},
                {"label": "Design", "max": 10},
            ],
        )
        # Order preserved
        self.assertEqual([c["label"] for c in tpl.categories], ["Introduction", "Method", "Design"])

    def test_can_create_category_with_grade_bands(self):
        """Categories can optionally use grade bands with auto-calculated thresholds."""
        tpl = AssessmentTemplate.objects.create(
            title="Advanced Template",
            module_code="KB5031",
            assessment_title="Coursework 1",
            categories=[
                {
                    "label": "Comprehension and application",
                    "max": 30,
                    "type": "grade",
                    "subdivision": "none"  # Just 1st, 2:1, 2:2, 3rd, Fail
                    # Thresholds auto-calculated: 1st=21-30, 2:1=18-20, 2:2=15-17, 3rd=12-14, Fail=0-11
                },
                {
                    "label": "Another Category",
                    "max": 20,
                    "type": "grade",
                    "subdivision": "high_low"  # High/Low for each grade
                    # Thresholds auto-calculated and subdivided
                },
                {
                    "label": "Simple Category",
                    "max": 10,
                    "type": "numeric"
                    # No bands for numeric type
                }
            ],
        )
        self.assertEqual(len(tpl.categories), 3)
        self.assertEqual(tpl.categories[0]["type"], "grade")
        self.assertEqual(tpl.categories[0]["subdivision"], "none")
        self.assertEqual(tpl.categories[1]["subdivision"], "high_low")
        self.assertEqual(tpl.categories[2]["type"], "numeric")

    def test_validate_categories_structure_and_bounds(self):
        """Model-level validation: non-empty list, labels non-blank, max in 1..1000 (or your chosen bound)."""
        # Empty list → invalid
        tpl = AssessmentTemplate(
            title="Empty",
            module_code="KB0000",
            assessment_title="Empty",
            categories=[],
        )
        with self.assertRaises(ValidationError):
            tpl.full_clean()

        # Bad rows → invalid
        tpl.categories = [
            {"label": "", "max": 10},          # blank label
            {"label": "Method", "max": "NaN"}, # non-numeric
            {"label": "Design", "max": -1},    # out of range
        ]
        with self.assertRaises(ValidationError):
            tpl.full_clean()

        # Valid again
        tpl.categories = [{"label": "OnlyOne", "max": 10, "type": "numeric"}]
        # Should not raise
        tpl.full_clean()

    def test_validate_grade_subdivision(self):
        """Grade categories must have valid subdivision values."""
        tpl = AssessmentTemplate(
            title="Test Bands",
            module_code="KB0000",
            assessment_title="Test",
            categories=[
                {
                    "label": "Category",
                    "max": 30,
                    "type": "grade",
                    "subdivision": "invalid"  # Invalid subdivision value
                }
            ],
        )
        with self.assertRaises(ValidationError):
            tpl.full_clean()

        # Numeric type shouldn't have subdivision
        tpl.categories = [
            {
                "label": "Category",
                "max": 10,
                "type": "numeric",
                "subdivision": "high_low"  # Numeric shouldn't have subdivision
            }
        ]
        with self.assertRaises(ValidationError):
            tpl.full_clean()

        # Grade type must have subdivision
        tpl.categories = [
            {
                "label": "Category",
                "max": 30,
                "type": "grade"
                # Missing subdivision
            }
        ]
        with self.assertRaises(ValidationError):
            tpl.full_clean()

    def test_calculate_grade_bands_no_subdivision(self):
        """Test grade band calculation with no subdivision (expanded to maximize mark coverage)."""
        from feedback.utils import calculate_grade_bands
        
        # For 30 marks: now includes expanded 1st and Fail bands (11 total)
        bands = calculate_grade_bands(30, "none")
        self.assertEqual(len(bands), 11)  # 11 bands total
        # Check key bands
        self.assertEqual(bands[0]["grade"], "Maximum 1st")
        self.assertEqual(bands[0]["marks"], 30)  # 100%
        self.assertEqual(bands[1]["grade"], "High 1st")
        self.assertEqual(bands[1]["marks"], 27)  # 90%
        self.assertEqual(bands[2]["grade"], "Mid 1st")
        self.assertEqual(bands[2]["marks"], 24)  # 80%
        self.assertEqual(bands[-1]["grade"], "Zero Fail")
        self.assertEqual(bands[-1]["marks"], 0)  # 0%

    def test_calculate_grade_bands_high_low_subdivision(self):
        """Test grade band calculation with high/low subdivision."""
        from feedback.utils import calculate_grade_bands
        
        # For 20 marks with high/low: each grade split within its band
        # Now includes expanded extremes: Maximum 1st + Close/Poor/Zero Fail
        bands = calculate_grade_bands(20, "high_low")
        self.assertEqual(len(bands), 13)  # Maximum 1st + 4 grades * 2 + 4 fail bands
        self.assertEqual(bands[0]["grade"], "Maximum 1st")
        self.assertEqual(bands[0]["marks"], 20)  # 100%
        self.assertEqual(bands[1]["grade"], "High 1st")
        self.assertEqual(bands[1]["marks"], 17)  # 85%
        self.assertEqual(bands[2]["grade"], "Low 1st")
        self.assertEqual(bands[2]["marks"], 14)  # 72%
        self.assertEqual(bands[-1]["grade"], "Zero Fail")
        self.assertEqual(bands[-1]["marks"], 0)  # 0%

    def test_calculate_grade_bands_high_mid_low_subdivision(self):
        """Test grade band calculation with high/mid/low subdivision."""
        from feedback.utils import calculate_grade_bands
        
        # For 30 marks with high/mid/low: each grade split in thirds
        # Now includes expanded extremes: Maximum 1st + Close/Poor/Zero Fail
        bands = calculate_grade_bands(30, "high_mid_low")
        self.assertEqual(len(bands), 17)  # Maximum 1st + 4 grades * 3 + 4 fail bands
        self.assertEqual(bands[0]["grade"], "Maximum 1st")
        self.assertEqual(bands[0]["marks"], 30)  # 100%
        self.assertEqual(bands[1]["grade"], "High 1st")
        self.assertEqual(bands[1]["marks"], 27)  # 90%
        self.assertEqual(bands[2]["grade"], "Mid 1st")
        self.assertEqual(bands[2]["marks"], 24)  # 80%
        self.assertEqual(bands[3]["grade"], "Low 1st")
        self.assertEqual(bands[3]["marks"], 21)  # 70%
        self.assertEqual(bands[-1]["grade"], "Zero Fail")
        self.assertEqual(bands[-1]["marks"], 0)  # 0%
    
    def test_calculate_grade_bands_finds_closest_valid_mark(self):
        """
        Test that grade band calculation finds the closest valid mark in the correct grade band.
        
        For 12 marks with 'none' subdivision:
        - Low 1st target: 70% × 12 = 8.4 rounds to 8
        - But 8/12 = 66.7% which is 2:1, not 1st
        - Should find 9/12 = 75% (valid 1st class) instead of going to 0
        """
        from feedback.utils import calculate_grade_bands
        
        bands = calculate_grade_bands(12, "none")
        self.assertEqual(len(bands), 11)
        
        # Extract marks for each band
        band_dict = {b["grade"]: b["marks"] for b in bands}
        
        # Maximum 1st should be 12 (100%)
        self.assertEqual(band_dict["Maximum 1st"], 12)
        
        # High 1st should be 11 (91.7% - valid 1st class)
        self.assertEqual(band_dict["High 1st"], 11)
        
        # Mid 1st should be 10 (83.3% - valid 1st class)
        self.assertEqual(band_dict["Mid 1st"], 10)
        
        # Low 1st should be 9 (75% - valid 1st class), NOT 0
        # This is the key test: 8.4 rounds to 8, but 8/12=66.7% is 2:1
        # So algorithm should find 9 as closest valid 1st class mark
        self.assertEqual(band_dict["Low 1st"], 9)
        
        # 2:1 should be 8 (66.7% - valid 2:1)
        self.assertEqual(band_dict["2:1"], 8)
        
        # All marks should be >= 0
        for band in bands:
            self.assertGreaterEqual(band["marks"], 0)
        
        # No duplicate marks except Zero Fail = 0
        non_zero_marks = [b["marks"] for b in bands if b["marks"] > 0]
        self.assertEqual(len(non_zero_marks), len(set(non_zero_marks)), 
                        "Found duplicate non-zero marks")
    
    def test_category_can_store_grade_band_descriptions(self):
        """Categories with grade bands can store descriptions for main grades (1st, 2:1, 2:2, 3rd, Fail).
        Maximum is included in 1st class, not separate."""
        tpl = AssessmentTemplate.objects.create(
            title="Test Template",
            module_code="KB5031",
            assessment_title="Test",
            categories=[
                {
                    "label": "Comprehension",
                    "max": 30,
                    "type": "grade",
                    "subdivision": "none",
                    "grade_band_descriptions": {
                        "1st": "Complex engineering principles are creatively and critically applied",
                        "2:1": "Well-founded engineering principles are soundly applied",
                        "2:2": "Basic application of engineering principles with limited understanding",
                        "3rd": "Basic engineering principles with minimal critical insight",
                        "Fail": "Basic engineering principles are inappropriately applied"
                    }
                }
            ]
        )
        tpl.full_clean()  # Should not raise
        self.assertIn("grade_band_descriptions", tpl.categories[0])
        self.assertEqual(len(tpl.categories[0]["grade_band_descriptions"]), 5)  # 5 main grades
        self.assertEqual(
            tpl.categories[0]["grade_band_descriptions"]["1st"],
            "Complex engineering principles are creatively and critically applied"
        )
