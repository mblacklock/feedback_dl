from django.db import models
from django.core.exceptions import ValidationError
import math


def calculate_grade_bands(max_marks, subdivision):
    """
    Calculate grade band thresholds based on UK grading percentages.
    
    UK Grade thresholds:
    - 1st: 70-100%
    - 2:1: 60-69%
    - 2:2: 50-59%
    - 3rd: 40-49%
    - Fail: 0-39%
    
    Args:
        max_marks: Maximum marks for this category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        List of dicts with grade, min, and max values
    """
    # Calculate base thresholds
    first_min = math.ceil(max_marks * 0.7)
    two_one_min = math.ceil(max_marks * 0.6)
    two_two_min = math.ceil(max_marks * 0.5)
    third_min = math.ceil(max_marks * 0.4)
    
    bands = []
    
    if subdivision == "none":
        # No subdivision - just 5 bands
        bands = [
            {"grade": "1st", "min": first_min, "max": max_marks},
            {"grade": "2:1", "min": two_one_min, "max": first_min - 1},
            {"grade": "2:2", "min": two_two_min, "max": two_one_min - 1},
            {"grade": "3rd", "min": third_min, "max": two_two_min - 1},
            {"grade": "Fail", "min": 0, "max": third_min - 1},
        ]
    
    elif subdivision == "high_low":
        # Split each grade band in half
        # 1st
        first_range = max_marks - first_min + 1
        first_mid = first_min + first_range // 2
        bands.append({"grade": "High 1st", "min": first_mid, "max": max_marks})
        bands.append({"grade": "Low 1st", "min": first_min, "max": first_mid - 1})
        
        # 2:1
        two_one_range = first_min - 1 - two_one_min + 1
        two_one_mid = two_one_min + two_one_range // 2
        bands.append({"grade": "High 2:1", "min": two_one_mid, "max": first_min - 1})
        bands.append({"grade": "Low 2:1", "min": two_one_min, "max": two_one_mid - 1})
        
        # 2:2
        two_two_range = two_one_min - 1 - two_two_min + 1
        two_two_mid = two_two_min + two_two_range // 2
        bands.append({"grade": "High 2:2", "min": two_two_mid, "max": two_one_min - 1})
        bands.append({"grade": "Low 2:2", "min": two_two_min, "max": two_two_mid - 1})
        
        # 3rd
        third_range = two_two_min - 1 - third_min + 1
        third_mid = third_min + third_range // 2
        bands.append({"grade": "High 3rd", "min": third_mid, "max": two_two_min - 1})
        bands.append({"grade": "Low 3rd", "min": third_min, "max": third_mid - 1})
        
        # Fail
        bands.append({"grade": "Fail", "min": 0, "max": third_min - 1})
    
    elif subdivision == "high_mid_low":
        # Split each grade band in thirds
        # 1st
        first_range = max_marks - first_min + 1
        first_third = first_range // 3
        bands.append({"grade": "High 1st", "min": max_marks - first_third + 1, "max": max_marks})
        bands.append({"grade": "Mid 1st", "min": max_marks - 2 * first_third + 1, "max": max_marks - first_third})
        bands.append({"grade": "Low 1st", "min": first_min, "max": max_marks - 2 * first_third})
        
        # 2:1
        two_one_range = first_min - 1 - two_one_min + 1
        two_one_third = two_one_range // 3
        bands.append({"grade": "High 2:1", "min": first_min - 1 - two_one_third + 1, "max": first_min - 1})
        bands.append({"grade": "Mid 2:1", "min": first_min - 1 - 2 * two_one_third + 1, "max": first_min - 1 - two_one_third})
        bands.append({"grade": "Low 2:1", "min": two_one_min, "max": first_min - 1 - 2 * two_one_third})
        
        # 2:2
        two_two_range = two_one_min - 1 - two_two_min + 1
        two_two_third = two_two_range // 3
        bands.append({"grade": "High 2:2", "min": two_one_min - 1 - two_two_third + 1, "max": two_one_min - 1})
        bands.append({"grade": "Mid 2:2", "min": two_one_min - 1 - 2 * two_two_third + 1, "max": two_one_min - 1 - two_two_third})
        bands.append({"grade": "Low 2:2", "min": two_two_min, "max": two_one_min - 1 - 2 * two_two_third})
        
        # 3rd
        third_range = two_two_min - 1 - third_min + 1
        third_third = third_range // 3
        bands.append({"grade": "High 3rd", "min": two_two_min - 1 - third_third + 1, "max": two_two_min - 1})
        bands.append({"grade": "Mid 3rd", "min": two_two_min - 1 - 2 * third_third + 1, "max": two_two_min - 1 - third_third})
        bands.append({"grade": "Low 3rd", "min": third_min, "max": two_two_min - 1 - 2 * third_third})
        
        # Fail
        bands.append({"grade": "Fail", "min": 0, "max": third_min - 1})
    
    return bands


class AssessmentTemplate(models.Model):
    title = models.CharField(max_length=200)
    module_code = models.CharField(max_length=50)
    assessment_title = models.CharField(max_length=200)
    categories = models.JSONField(default=list)

    def clean(self):
        """Validate categories structure and bounds."""
        super().clean()
        
        if not self.categories:
            raise ValidationError("At least one category is required")
        
        errors = []
        VALID_TYPES = ["numeric", "grade"]
        VALID_SUBDIVISIONS = ["none", "high_low", "high_mid_low"]
        
        for idx, cat in enumerate(self.categories):
            cat_num = idx + 1
            
            # Check label is not blank
            if not cat.get("label", "").strip():
                errors.append(f"Category {cat_num}: label cannot be blank")
            
            # Check max is numeric and in valid range
            try:
                max_val = int(cat.get("max", 0))
                if max_val < 1 or max_val > 1000:
                    errors.append(f"Category {cat_num}: max must be between 1 and 1000")
            except (ValueError, TypeError):
                errors.append(f"Category {cat_num}: max must be a number")
                continue
            
            # Check type is valid (default to numeric for backward compatibility)
            cat_type = cat.get("type", "numeric")
            if cat_type not in VALID_TYPES:
                errors.append(f"Category {cat_num}: type must be 'numeric' or 'grade'")
            
            # Validate grade-specific fields
            if cat_type == "grade":
                subdivision = cat.get("subdivision")
                if not subdivision:
                    errors.append(f"Category {cat_num}: grade type requires 'subdivision' field")
                elif subdivision not in VALID_SUBDIVISIONS:
                    errors.append(f"Category {cat_num}: subdivision must be one of {VALID_SUBDIVISIONS}")
            
            # Numeric types shouldn't have subdivision
            if cat_type == "numeric" and cat.get("subdivision"):
                errors.append(f"Category {cat_num}: numeric type cannot have subdivision")
        
        if errors:
            raise ValidationError(errors)