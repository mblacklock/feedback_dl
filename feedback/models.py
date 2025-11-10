from django.db import models
from django.core.exceptions import ValidationError


class AssessmentTemplate(models.Model):
    component = models.IntegerField()
    title = models.CharField(max_length=200)
    module_code = models.CharField(max_length=50)
    module_title = models.CharField(max_length=200, blank=True, default='')
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