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
        """Test grade band calculation with no subdivision (basic 5 bands)."""
        from feedback.models import calculate_grade_bands
        
        # For 30 marks: 1st>=21, 2:1>=18, 2:2>=15, 3rd>=12, Fail<12
        bands = calculate_grade_bands(30, "none")
        self.assertEqual(bands, [
            {"grade": "1st", "min": 21, "max": 30},
            {"grade": "2:1", "min": 18, "max": 20},
            {"grade": "2:2", "min": 15, "max": 17},
            {"grade": "3rd", "min": 12, "max": 14},
            {"grade": "Fail", "min": 0, "max": 11},
        ])

    def test_calculate_grade_bands_high_low_subdivision(self):
        """Test grade band calculation with high/low subdivision."""
        from feedback.models import calculate_grade_bands
        
        # For 20 marks with high/low: each grade gets split in half
        bands = calculate_grade_bands(20, "high_low")
        # 1st: 14-20 (70-100%) -> High 1st: 17-20, Low 1st: 14-16
        # 2:1: 12-13 (60-69%) -> High 2:1: 13, Low 2:1: 12
        # 2:2: 10-11 (50-59%) -> High 2:2: 11, Low 2:2: 10
        # 3rd: 8-9 (40-49%) -> High 3rd: 9, Low 3rd: 8
        # Fail: 0-7 (<40%)
        self.assertEqual(len(bands), 9)  # 4 grades * 2 + Fail
        self.assertEqual(bands[0]["grade"], "High 1st")
        self.assertEqual(bands[0]["min"], 17)
        self.assertEqual(bands[0]["max"], 20)
        self.assertEqual(bands[-1]["grade"], "Fail")

    def test_calculate_grade_bands_high_mid_low_subdivision(self):
        """Test grade band calculation with high/mid/low subdivision."""
        from feedback.models import calculate_grade_bands
        
        # For 30 marks with high/mid/low: each grade gets split in thirds
        bands = calculate_grade_bands(30, "high_mid_low")
        # 1st: 21-30 (10 marks) -> High: 27-30, Mid: 24-26, Low: 21-23
        self.assertEqual(len(bands), 13)  # 4 grades * 3 + Fail
        self.assertEqual(bands[0]["grade"], "High 1st")
        self.assertEqual(bands[1]["grade"], "Mid 1st")
        self.assertEqual(bands[2]["grade"], "Low 1st")
