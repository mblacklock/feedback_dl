from django.db import models
from django.core.exceptions import ValidationError
from math import floor


def _round_marks(value):
    """Traditional rounding (always round 0.5 up) for grade marks."""
    return int(floor(value + 0.5))


def calculate_grade_bands(max_marks, subdivision):
    """
    Calculate grade band mark values based on UK grading percentages.
    
    UK Grade thresholds:
    - 1st: 70-100%
    - 2:1: 60-69%
    - 2:2: 50-59%
    - 3rd: 40-49%
    - Fail: 0-39%
    
    Returns a single representative mark value for each grade band.
    
    Args:
        max_marks: Maximum marks for this category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        List of dicts with grade and marks (single integer value)
    """
    bands = []
    
    if subdivision == "none":
        # No subdivision - use midpoint of each band
        # 1st: 85% (midpoint of 70-100%)
        # 2:1: 65% (midpoint of 60-69%)
        # 2:2: 55% (midpoint of 50-59%)
        # 3rd: 45% (midpoint of 40-49%)
        # Fail: 20% (midpoint of 0-39%)
        bands = [
            {"grade": "1st", "marks": _round_marks(max_marks * 0.85)},
            {"grade": "2:1", "marks": _round_marks(max_marks * 0.65)},
            {"grade": "2:2", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "3rd", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
    elif subdivision == "high_low":
        # High/Low subdivision - use 85% and 75% for High/Low of each band
        # High 1st: 85%, Low 1st: 75%
        # High 2:1: 65%, Low 2:1: 55%
        # High 2:2: 55%, Low 2:2: 45%
        # High 3rd: 45%, Low 3rd: 35%
        # Fail: 20%
        bands = [
            {"grade": "High 1st", "marks": _round_marks(max_marks * 0.85)},
            {"grade": "Low 1st", "marks": _round_marks(max_marks * 0.75)},
            {"grade": "High 2:1", "marks": _round_marks(max_marks * 0.65)},
            {"grade": "Low 2:1", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "High 2:2", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "Low 2:2", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "High 3rd", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "Low 3rd", "marks": _round_marks(max_marks * 0.35)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
    elif subdivision == "high_mid_low":
        # High/Mid/Low subdivision - use 90%, 80%, 70% etc for High/Mid/Low of each band
        # High 1st: 90%, Mid 1st: 80%, Low 1st: 70%
        # High 2:1: 67%, Mid 2:1: 63%, Low 2:1: 60%
        # High 2:2: 57%, Mid 2:2: 53%, Low 2:2: 50%
        # High 3rd: 47%, Mid 3rd: 43%, Low 3rd: 40%
        # Fail: 20%
        bands = [
            {"grade": "High 1st", "marks": _round_marks(max_marks * 0.90)},
            {"grade": "Mid 1st", "marks": _round_marks(max_marks * 0.80)},
            {"grade": "Low 1st", "marks": _round_marks(max_marks * 0.70)},
            {"grade": "High 2:1", "marks": _round_marks(max_marks * 0.67)},
            {"grade": "Mid 2:1", "marks": _round_marks(max_marks * 0.63)},
            {"grade": "Low 2:1", "marks": _round_marks(max_marks * 0.60)},
            {"grade": "High 2:2", "marks": _round_marks(max_marks * 0.57)},
            {"grade": "Mid 2:2", "marks": _round_marks(max_marks * 0.53)},
            {"grade": "Low 2:2", "marks": _round_marks(max_marks * 0.50)},
            {"grade": "High 3rd", "marks": _round_marks(max_marks * 0.47)},
            {"grade": "Mid 3rd", "marks": _round_marks(max_marks * 0.43)},
            {"grade": "Low 3rd", "marks": _round_marks(max_marks * 0.40)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
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