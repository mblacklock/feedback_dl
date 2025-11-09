from django.test import TestCase
from feedback.utils import calculate_grade_bands, validate_subdivision


class GradeBandUtilsTests(TestCase):
    """Tests for grade band utility functions."""
    
    def test_validate_subdivision_none_valid_for_sufficient_marks(self):
        """Test that 'none' subdivision is valid for 10+ marks."""
        self.assertTrue(validate_subdivision(10, "none"))
        self.assertTrue(validate_subdivision(20, "none"))
        self.assertTrue(validate_subdivision(30, "none"))
    
    def test_validate_subdivision_none_invalid_for_low_marks(self):
        """Test that 'none' subdivision is invalid for very low marks where bands overlap."""
        # 5 marks: 2:1 (3.25→3) = 2:2 (2.75→3)
        self.assertFalse(validate_subdivision(5, "none"))
        # 6 marks: also has overlaps
        self.assertFalse(validate_subdivision(6, "none"))
    
    def test_validate_subdivision_high_low_invalid_for_most_cases(self):
        """Test that 'high_low' subdivision creates overlaps in most cases."""
        # Even at 20 marks, high_low creates overlaps (e.g., Low 2:1 = High 2:2)
        self.assertFalse(validate_subdivision(10, "high_low"))
        self.assertFalse(validate_subdivision(20, "high_low"))
    
    def test_validate_subdivision_high_mid_low_valid_for_high_marks(self):
        """Test that 'high_mid_low' subdivision is valid for 30+ marks."""
        self.assertTrue(validate_subdivision(30, "high_mid_low"))
        self.assertTrue(validate_subdivision(40, "high_mid_low"))
    
    def test_validate_subdivision_high_mid_low_invalid_for_low_marks(self):
        """Test that 'high_mid_low' subdivision is invalid for low marks."""
        self.assertFalse(validate_subdivision(10, "high_mid_low"))
        self.assertFalse(validate_subdivision(20, "high_mid_low"))
