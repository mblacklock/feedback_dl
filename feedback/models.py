from django.db import models
from django.core.exceptions import ValidationError


class AssessmentTemplate(models.Model):
    component = models.IntegerField()
    title = models.CharField(max_length=200)
    module_code = models.CharField(max_length=50)
    module_title = models.CharField(max_length=200)
    assessment_title = models.CharField(max_length=200)
    weighting = models.IntegerField(help_text="Assessment weighting as percentage (e.g., 40 for 40%)")
    max_marks = models.IntegerField(help_text="Maximum marks for the assessment (e.g., 100)")
    categories = models.JSONField(default=list)
    charts = models.JSONField(
        default=list,
        blank=True,
        help_text="Chart configurations for feedback sheet (e.g., histograms, radar charts)"
    )

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
        
        # Validate charts
        if self.charts:
            VALID_CHART_TYPES = ["histogram", "radar"]
            
            for idx, chart in enumerate(self.charts):
                chart_num = idx + 1
                
                # Check chart type
                chart_type = chart.get("type")
                if not chart_type:
                    errors.append(f"Chart {chart_num}: 'type' is required")
                elif chart_type not in VALID_CHART_TYPES:
                    errors.append(f"Chart {chart_num}: type must be one of {VALID_CHART_TYPES}")
                
                # Check title
                if not chart.get("title", "").strip():
                    errors.append(f"Chart {chart_num}: 'title' cannot be blank")
                
                # Validate data source based on chart type
                if chart_type == "radar":
                    # Radar needs list of category labels
                    categories = chart.get("categories", [])
                    if not categories or not isinstance(categories, list):
                        errors.append(f"Chart {chart_num}: radar chart requires 'categories' list")
                    else:
                        # Check that referenced categories exist
                        category_labels = [cat.get("label") for cat in self.categories]
                        for cat_label in categories:
                            if cat_label not in category_labels:
                                errors.append(f"Chart {chart_num}: category '{cat_label}' not found in template")
                
                elif chart_type == "histogram":
                    # Histogram needs data source
                    data_source = chart.get("data_source")
                    if not data_source:
                        errors.append(f"Chart {chart_num}: 'histogram' requires 'data_source' field")
                    elif data_source != "overall":
                        # Check if it's a valid category label
                        category_labels = [cat.get("label") for cat in self.categories]
                        if data_source not in category_labels:
                            errors.append(f"Chart {chart_num}: data_source '{data_source}' must be 'overall' or a valid category label")
        
        if errors:
            raise ValidationError(errors)