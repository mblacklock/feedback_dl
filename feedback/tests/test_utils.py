from django.test import TestCase
from feedback.utils import calculate_grade_bands, validate_subdivision


class GradeBandUtilsTests(TestCase):
    """Tests for grade band utility functions."""
    
    def test_validate_subdivision_none_valid_for_sufficient_marks(self):
        """Test that 'none' subdivision is valid for 10+ marks."""
        self.assertTrue(validate_subdivision(10, "none"))
        self.assertTrue(validate_subdivision(20, "none"))
        self.assertTrue(validate_subdivision(30, "none"))
    
    def test_validate_subdivision_none_invalid_for_very_low_marks(self):
        """Test that 'none' subdivision is invalid for marks under 9.
        
        The improved algorithm can handle 9+ marks by finding the closest valid
        mark in each grade band, even if it produces some duplicate marks within
        a grade (e.g., Mid 1st = Low 1st = 7 for 9 marks).
        """
        # Very low marks still invalid
        self.assertFalse(validate_subdivision(5, "none"))
        self.assertFalse(validate_subdivision(7, "none"))
        
        # 9 marks now valid with improved algorithm (allows duplicates within grade)
        self.assertTrue(validate_subdivision(9, "none"))
    
    def test_validate_subdivision_high_low_valid_for_sufficient_marks(self):
        """Test that 'high_low' subdivision is valid for 20+ marks."""
        self.assertTrue(validate_subdivision(20, "high_low"))
        self.assertTrue(validate_subdivision(30, "high_low"))
    
    def test_validate_subdivision_high_low_valid_for_low_marks_with_duplicates(self):
        """Test that 'high_low' subdivision allows duplicates within same grade."""
        # 10 marks produces High 2:1 = Low 2:1 = 6, which is pedagogically acceptable
        self.assertTrue(validate_subdivision(10, "high_low"))
    
    def test_validate_subdivision_high_mid_low_valid_for_high_marks(self):
        """Test that 'high_mid_low' subdivision is valid for 30+ marks."""
        self.assertTrue(validate_subdivision(30, "high_mid_low"))
        self.assertTrue(validate_subdivision(40, "high_mid_low"))
    
    def test_validate_subdivision_high_mid_low_valid_for_various_marks(self):
        """Test that 'high_mid_low' subdivision is valid for 10+ marks (allows duplicates)."""
        self.assertTrue(validate_subdivision(10, "high_mid_low"))
        self.assertTrue(validate_subdivision(20, "high_mid_low"))
