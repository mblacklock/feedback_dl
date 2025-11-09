from django.shortcuts import render, redirect
from feedback.models import AssessmentTemplate
from feedback.utils import calculate_grade_bands, validate_subdivision

def home(request):
    return render(request, "feedback/home.html", {"page_title": "Feedback"})

def template_new(request):
    # If GET request, create minimal template and redirect to edit page  
    # If POST request, use legacy form submission (for backwards compatibility with tests)
    if request.method == "POST":
        # Extract form data
        title = request.POST.get("title", "").strip()
        module_code = request.POST.get("module_code", "").strip()
        assessment_title = request.POST.get("assessment_title", "").strip()
        category_labels = request.POST.getlist("category_label")
        category_maxes = request.POST.getlist("category_max")
        category_types = request.POST.getlist("category_type")
        category_subdivisions = request.POST.getlist("category_subdivision")
        
        errors = []
        categories = []
        
        # Validate required fields
        if not title:
            errors.append("Title is required")
        if not module_code:
            errors.append("Module code is required")
        if not assessment_title:
            errors.append("Assessment title is required")
        
        # Validate and build categories list
        for idx, (label, max_val) in enumerate(zip(category_labels, category_maxes)):
            # Skip completely empty rows
            if not label.strip() and not max_val.strip():
                continue
                
            # Check for blank label
            if not label.strip():
                errors.append("Category labels cannot be blank")
                continue
            
            # Validate max value
            try:
                max_int = int(max_val)
                if max_int < 1 or max_int > 1000:
                    errors.append("Max marks must be a number between 1 and 1000")
                    continue
            except (ValueError, TypeError):
                errors.append("Max marks must be a number between 1 and 1000")
                continue
            
            # Build category dict
            cat = {
                "label": label,
                "max": max_int
            }
            
            # Add type and subdivision if provided
            cat_type = category_types[idx] if idx < len(category_types) else "numeric"
            cat["type"] = cat_type
            
            # Only add subdivision for grade types
            if cat_type == "grade":
                subdivision = category_subdivisions[idx] if idx < len(category_subdivisions) else ""
                if subdivision:
                    # Validate that this subdivision doesn't create overlapping bands
                    if not validate_subdivision(max_int, subdivision):
                        errors.append(
                            f"Category '{label}': {max_int} marks is too low for subdivision. "
                            f"This would result in impossible grade bands, e.g. for 5 marks, a 2:2 is not possible. "
                            f"Use 10+ marks or switch to numeric scoring."
                        )
                        continue
                    cat["subdivision"] = subdivision
            
            categories.append(cat)
        
        # Check we have at least one category
        if not categories:
            errors.append("At least one category is required")
        
        # If there are errors, re-render form
        if errors:
            return render(request, "feedback/template_new.html", {"errors": errors})
        
        # Create the template
        tpl = AssessmentTemplate.objects.create(
            title=title,
            module_code=module_code,
            assessment_title=assessment_title,
            categories=categories
        )
        
        return redirect("template_summary", pk=tpl.id)
    
    # GET request - create minimal template and redirect to edit page
    tpl = AssessmentTemplate.objects.create(
        title="Untitled Template",
        module_code="",
        assessment_title="",
        categories=[]
    )
    return redirect("template_edit", pk=tpl.id)

def template_edit(request, pk):
    """Edit page with auto-save functionality."""
    import json
    tpl = AssessmentTemplate.objects.get(pk=pk)
    return render(request, "feedback/template_edit.html", {
        "template": tpl,
        "categories_json": json.dumps(tpl.categories if tpl.categories else [])
    })

def template_update(request, pk):
    """AJAX endpoint for auto-saving template updates."""
    import json
    from django.http import JsonResponse
    
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    
    tpl = AssessmentTemplate.objects.get(pk=pk)
    data = json.loads(request.body)
    
    # Update fields if provided
    if "title" in data:
        tpl.title = data["title"]
    if "module_code" in data:
        tpl.module_code = data["module_code"]
    if "assessment_title" in data:
        tpl.assessment_title = data["assessment_title"]
    if "categories" in data:
        tpl.categories = data["categories"]
    
    try:
        tpl.save()
        return JsonResponse({"status": "saved"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def grade_bands_preview(request):
    """AJAX endpoint to calculate grade bands for preview."""
    from django.http import JsonResponse
    from django.template.loader import render_to_string
    
    try:
        max_marks = int(request.GET.get('max_marks', 0))
        subdivision = request.GET.get('subdivision', '')
        
        if max_marks < 1 or not subdivision:
            return JsonResponse({"html": ""})
        
        bands = calculate_grade_bands(max_marks, subdivision)
        grouped_bands = _group_bands_by_main_grade(bands)
        
        # Render HTML template
        html = render_to_string('feedback/partials/grade_bands_preview.html', {
            'grouped_bands': grouped_bands,
            'descriptions': {}  # Empty for preview, will be filled by JS from existing data
        })
        
        return JsonResponse({"html": html})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def template_summary(request, pk):
    tpl = AssessmentTemplate.objects.get(pk=pk)
    
    # Calculate grade bands for each category
    categories_with_bands = []
    for cat in tpl.categories:
        cat_data = cat.copy()
        if cat.get("type") == "grade" and cat.get("subdivision"):
            bands = calculate_grade_bands(cat["max"], cat["subdivision"])
            cat_data["bands"] = bands
            
            # Group bands by main grade for display
            grouped_bands = _group_bands_by_main_grade(bands)
            cat_data["grouped_bands"] = grouped_bands
            
            # Attach descriptions (one per main grade)
            descriptions = cat.get("grade_band_descriptions", {})
            cat_data["grade_descriptions"] = descriptions
            
        categories_with_bands.append(cat_data)
    
    return render(request, "feedback/template_summary.html", {
        "template": tpl,
        "categories_with_bands": categories_with_bands
    })

def _group_bands_by_main_grade(bands):
    """Group bands by main grade (1st, 2:1, 2:2, 3rd, Fail).
    'Maximum 1st' is grouped with other '1st' bands."""
    main_grades = ["1st", "2:1", "2:2", "3rd", "Fail"]
    grouped = {}
    
    for band in bands:
        # Find which main grade this band belongs to
        main_grade = None
        for grade in main_grades:
            if grade in band["grade"]:
                main_grade = grade
                break
        
        if main_grade:
            if main_grade not in grouped:
                grouped[main_grade] = []
            grouped[main_grade].append(band)
    
    return grouped