from django.shortcuts import render, redirect
from django.http import JsonResponse
from feedback.models import AssessmentTemplate
from feedback.utils import calculate_grade_bands, validate_subdivision

def home(request):
    templates = AssessmentTemplate.objects.all().order_by('-id')
    return render(request, "feedback/home.html", {
        "page_title": "Feedback",
        "templates": templates
    })

def template_new(request):
    """Create a new template and redirect to edit page."""
    tpl = AssessmentTemplate.objects.create(
        component=1,
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
    if "module_title" in data:
        tpl.module_title = data["module_title"]
    if "assessment_title" in data:
        tpl.assessment_title = data["assessment_title"]
    if "weighting" in data:
        tpl.weighting = data["weighting"]
    if "component" in data:
        tpl.component = data["component"]
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
        html = render_to_string('feedback/partials/grade_bands_grid.html', {
            'grouped_bands': grouped_bands,
            'descriptions': {},  # Empty for preview, will be filled by JS from existing data
            'show_textarea': True
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

def template_delete(request, pk):
    """AJAX endpoint to delete a template."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    
    try:
        tpl = AssessmentTemplate.objects.get(pk=pk)
        tpl.delete()
        return JsonResponse({"status": "deleted"})
    except AssessmentTemplate.DoesNotExist:
        return JsonResponse({"error": "Template not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

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