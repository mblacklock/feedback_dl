from django.shortcuts import render, redirect
from django.http import JsonResponse
from feedback.models import AssessmentTemplate
from feedback.utils import calculate_grade_bands, validate_subdivision

import random

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
        module_title="",
        assessment_title="",
        weighting=0,
        max_marks=0,
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
    if "max_marks" in data:
        tpl.max_marks = data["max_marks"]
    if "component" in data:
        tpl.component = data["component"]
    if "categories" in data:
        tpl.categories = data["categories"]
    if "charts" in data:
        tpl.charts = data["charts"]
    # Persist degree level if provided by autosave
    if "degree_level" in data:
        tpl.degree_level = data["degree_level"]
    
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
        degree_level = request.GET.get('degree_level', None)
        
        if max_marks < 1 or not subdivision:
            return JsonResponse({"html": ""})
        
        bands = calculate_grade_bands(max_marks, subdivision, degree_level=degree_level)
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

def template_rubric(request, pk):
    """View rubric for pasting into assessment briefs"""
    tpl = AssessmentTemplate.objects.get(pk=pk)
    
    # Calculate grade bands for each category
    categories_with_bands = []
    total_category_marks = 0
    for cat in tpl.categories:
        cat_data = cat.copy()
        total_category_marks += cat.get("max", 0)
        
        if cat.get("type") == "grade" and cat.get("subdivision"):
            bands = calculate_grade_bands(cat["max"], cat["subdivision"], degree_level=tpl.degree_level)
            cat_data["bands"] = bands
            
            # Group bands by main grade for display
            grouped_bands = _group_bands_by_main_grade(bands)
            cat_data["grouped_bands"] = grouped_bands
            
            # Attach descriptions (one per main grade)
            descriptions = cat.get("grade_band_descriptions", {})
            cat_data["grade_descriptions"] = descriptions
            
        categories_with_bands.append(cat_data)
    
    # Check if marks match
    marks_mismatch = None
    if tpl.max_marks and total_category_marks != tpl.max_marks:
        marks_mismatch = {
            'total': total_category_marks,
            'max_marks': tpl.max_marks
        }
    
    return render(request, "feedback/template_rubric.html", {
        "template": tpl,
        "categories_with_bands": categories_with_bands,
        "marks_mismatch": marks_mismatch
    })

def template_feedback_sheet(request, pk):
    """View example feedback sheet for students"""
    """Marks are randomly generated"""
    tpl = AssessmentTemplate.objects.get(pk=pk)
    
    # Calculate grade bands for each category (for reference)
    categories_with_bands = []
    total_category_marks = 0
    for cat in tpl.categories:
        cat_data = cat.copy()
        total_category_marks += cat.get("max", 0)
        
        if cat.get("type") == "grade" and cat.get("subdivision"):
            bands = calculate_grade_bands(cat["max"], cat["subdivision"], degree_level=tpl.degree_level)
            cat_data["bands"] = bands
            grouped_bands = _group_bands_by_main_grade(bands)
            cat_data["grouped_bands"] = grouped_bands
            # Pick a deterministic example grade for this category using a RNG
            # seeded from the template id so example sheets are repeatable per-template.
            try:
                rng = random.Random(tpl.pk)
                chosen = rng.choice(bands) if bands else None
                if chosen:
                    # store an example grade and marks for template display
                    cat_data["awarded_grade"] = chosen.get("grade")
                    cat_data["awarded_mark"] = chosen.get("marks")
                else:
                    cat_data["awarded_grade"] = None
                    cat_data["awarded_mark"] = None
            except Exception:
                cat_data["awarded_grade"] = None
                cat_data["awarded_mark"] = None           
        else:
            # For numeric categories, provide an example awarded mark for the sample sheet
            cat_data["awarded_grade"] = None
            try:
                rng = random.Random(tpl.pk)
                max_marks = int(cat.get("max", 0)) if cat.get("max") is not None else 0
                if max_marks > 0:
                    # pick a deterministic example between 0 and max using seeded RNG
                    cat_data["awarded_mark"] = rng.randint(0, max_marks)
                else:
                    cat_data["awarded_mark"] = None
            except Exception:
                cat_data["awarded_mark"] = None
        categories_with_bands.append(cat_data)
    
    # Check if the sum of the category marks match the assessment max_marks
    marks_mismatch = None
    if total_category_marks != tpl.max_marks:
        marks_mismatch = {
            'total': total_category_marks,
            'max_marks': tpl.max_marks
        }

    # Calculate overall grade for the assessment
    try:
        from feedback.utils import grade_for_percentage

        display_max = total_category_marks if total_category_marks > 0 else 0 # use total of maxima forcategories
        assessment_mark = None
        if display_max > 0:
            # Compute the total awarded mark as the sum of per-category awarded
            total_awarded_mark = 0
            for c in categories_with_bands:
                m = c.get("awarded_mark")
                try:
                    if m is not None:
                        total_awarded_mark += int(m)
                except Exception:
                    # ignore non-integer/example values
                    continue

            assessment_mark = total_awarded_mark
            # Derive an example grade band from the percentage of the total available marks
            try:
                percentage = (assessment_mark / display_max) * 100
                grade = grade_for_percentage(percentage)
            except Exception:
                grade = None
            assessment_grade = grade
    except Exception:
        assessment_grade = None

    # Add awarded_mark_percentage to each category
    for category in categories_with_bands:
        max_marks = category.get("max", 0)
        awarded_mark = category.get("awarded_mark", 0)
        if max_marks > 0:
            category["awarded_mark_percentage"] = (awarded_mark / max_marks) * 100
        else:
            category["awarded_mark_percentage"] = 0

    # Update charts to include categories_with_bands
    charts = tpl.charts if tpl.charts else []
    # Add assessment_mark to each chart
    for chart in charts:
        if chart['type'] == 'histogram':
            chart['student_mark'] = assessment_mark
    # Map awarded marks to radar chart categories while keeping labels
    for chart in charts:
        if chart['type'] == 'radar':
            chart['awarded_cat_percentages'] = [
                next((cat['awarded_mark_percentage'] for cat in categories_with_bands if cat['label'] == label), 0) for label in chart['categories']
            ]

    return render(request, "feedback/template_feedback_sheet.html", {
        "template": tpl,
        "categories_with_bands": categories_with_bands,
        "total_marks": total_category_marks,
        "assessment_grade": assessment_grade,
        "assessment_awarded": assessment_mark,
        "charts": tpl.charts if tpl.charts else [],
        "marks_mismatch": marks_mismatch
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
    """Group bands by main grade.

    Supports both undergraduate main grades ("1st", "2:1", "2:2", "3rd", "Fail")
    and postgraduate main grades ("Distinction", "Merit", "Pass", "Fail"). The
    function inspects band labels to decide which set to use.
    'Maximum 1st' is grouped with other '1st' bands (or 'Distinction' bands when
    remapped).
    """
    # Determine if bands appear to be postgraduate-labelled
    pg_indicators = ('Distinction', 'Merit', 'Pass')
    use_pg = any(any(ind in band['grade'] for ind in pg_indicators) for band in bands)

    if use_pg:
        main_grades = ["Distinction", "Merit", "Pass", "Fail"]
    else:
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
            grouped.setdefault(main_grade, []).append(band)
    
    return grouped
from django.shortcuts import render, redirect
from django.http import JsonResponse
from feedback.models import AssessmentTemplate
from feedback.utils import calculate_grade_bands, validate_subdivision

import random

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
        module_title="",
        assessment_title="",
        weighting=0,
        max_marks=0,
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
    # (no debug prints) - receive data but do not log to stdout in tests
    
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
    if "max_marks" in data:
        tpl.max_marks = data["max_marks"]
    if "component" in data:
        tpl.component = data["component"]
    if "categories" in data:
        tpl.categories = data["categories"]
    if "charts" in data:
        tpl.charts = data["charts"]
    # Persist degree level if provided by autosave
    if "degree_level" in data:
        tpl.degree_level = data["degree_level"]
    
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
        degree_level = request.GET.get('degree_level', None)
        
        if max_marks < 1 or not subdivision:
            return JsonResponse({"html": ""})
        
        bands = calculate_grade_bands(max_marks, subdivision, degree_level=degree_level)
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

def template_rubric(request, pk):
    """View rubric for pasting into assessment briefs"""
    tpl = AssessmentTemplate.objects.get(pk=pk)
    
    # Calculate grade bands for each category
    categories_with_bands = []
    total_category_marks = 0
    for cat in tpl.categories:
        cat_data = cat.copy()
        total_category_marks += cat.get("max", 0)
        
        if cat.get("type") == "grade" and cat.get("subdivision"):
            bands = calculate_grade_bands(cat["max"], cat["subdivision"], degree_level=tpl.degree_level)
            cat_data["bands"] = bands
            
            # Group bands by main grade for display
            grouped_bands = _group_bands_by_main_grade(bands)
            cat_data["grouped_bands"] = grouped_bands
            
            # Attach descriptions (one per main grade)
            descriptions = cat.get("grade_band_descriptions", {})
            cat_data["grade_descriptions"] = descriptions
            
        categories_with_bands.append(cat_data)
    
    # Check if marks match
    marks_mismatch = None
    if tpl.max_marks and total_category_marks != tpl.max_marks:
        marks_mismatch = {
            'total': total_category_marks,
            'max_marks': tpl.max_marks
        }
    
    return render(request, "feedback/template_rubric.html", {
        "template": tpl,
        "categories_with_bands": categories_with_bands,
        "marks_mismatch": marks_mismatch
    })

def template_feedback_sheet(request, pk):
    """View example feedback sheet for students"""
    """Marks are randomly generated"""
    tpl = AssessmentTemplate.objects.get(pk=pk)
    
    # Calculate grade bands for each category (for reference)
    categories_with_bands = []
    total_category_marks = 0
    for cat in tpl.categories:
        cat_data = cat.copy()
        total_category_marks += cat.get("max", 0)
        
        if cat.get("type") == "grade" and cat.get("subdivision"):
            bands = calculate_grade_bands(cat["max"], cat["subdivision"], degree_level=tpl.degree_level)
            cat_data["bands"] = bands
            grouped_bands = _group_bands_by_main_grade(bands)
            cat_data["grouped_bands"] = grouped_bands
            # Pick a deterministic example grade for this category using a RNG
            # seeded from the template id so example sheets are repeatable per-template.
            try:
                rng = random.Random(tpl.pk)
                chosen = rng.choice(bands) if bands else None
                if chosen:
                    # store an example grade and marks for template display
                    cat_data["awarded_grade"] = chosen.get("grade")
                    cat_data["awarded_mark"] = chosen.get("marks")
                else:
                    cat_data["awarded_grade"] = None
                    cat_data["awarded_mark"] = None
            except Exception:
                cat_data["awarded_grade"] = None
                cat_data["awarded_mark"] = None           
        else:
            # For numeric categories, provide an example awarded mark for the sample sheet
            cat_data["awarded_grade"] = None
            try:
                rng = random.Random(tpl.pk)
                max_marks = int(cat.get("max", 0)) if cat.get("max") is not None else 0
                if max_marks > 0:
                    # pick a deterministic example between 0 and max using seeded RNG
                    cat_data["awarded_mark"] = rng.randint(0, max_marks)
                else:
                    cat_data["awarded_mark"] = None
            except Exception:
                cat_data["awarded_mark"] = None
        categories_with_bands.append(cat_data)
    
    # Check if the sum of the category marks match the assessment max_marks
    marks_mismatch = None
    if total_category_marks != tpl.max_marks:
        marks_mismatch = {
            'total': total_category_marks,
            'max_marks': tpl.max_marks
        }

    # Calculate overall grade for the assessment
    try:
        from feedback.utils import grade_for_percentage

        display_max = total_category_marks if total_category_marks > 0 else 0 # use total of maxima forcategories
        assessment_mark = None
        if display_max > 0:
            # Compute the total awarded mark as the sum of per-category awarded
            total_awarded_mark = 0
            for c in categories_with_bands:
                m = c.get("awarded_mark")
                try:
                    if m is not None:
                        total_awarded_mark += int(m)
                except Exception:
                    # ignore non-integer/example values
                    continue

            assessment_mark = total_awarded_mark
            # Derive an example grade band from the percentage of the total available marks
            try:
                percentage = (assessment_mark / display_max) * 100
                grade = grade_for_percentage(percentage)
            except Exception:
                grade = None
            assessment_grade = grade
    except Exception:
        assessment_grade = None

    # Add awarded_mark_percentage to each category
    for category in categories_with_bands:
        max_marks = category.get("max", 0)
        awarded_mark = category.get("awarded_mark", 0)
        if max_marks > 0:
            category["awarded_mark_percentage"] = (awarded_mark / max_marks) * 100
        else:
            category["awarded_mark_percentage"] = 0

    # Update charts to include categories_with_bands
    charts = tpl.charts if tpl.charts else []
    # Add assessment_mark to each chart
    for chart in charts:
        if chart['type'] == 'histogram':
            chart['student_mark'] = assessment_mark
    # Map awarded marks to radar chart categories while keeping labels
    for chart in charts:
        if chart['type'] == 'radar':
            chart['awarded_cat_percentages'] = [
                next((cat['awarded_mark_percentage'] for cat in categories_with_bands if cat['label'] == label), 0) for label in chart['categories']
            ]

    return render(request, "feedback/template_feedback_sheet.html", {
        "template": tpl,
        "categories_with_bands": categories_with_bands,
        "total_marks": total_category_marks,
        "assessment_grade": assessment_grade,
        "assessment_awarded": assessment_mark,
        "charts": tpl.charts if tpl.charts else [],
        "marks_mismatch": marks_mismatch
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
    """Group bands by main grade.

    Supports both undergraduate main grades ("1st", "2:1", "2:2", "3rd", "Fail")
    and postgraduate main grades ("Distinction", "Merit", "Pass", "Fail"). The
    function inspects band labels to decide which set to use.
    'Maximum 1st' is grouped with other '1st' bands (or 'Distinction' bands when
    remapped).
    """
    # Determine if bands appear to be postgraduate-labelled
    pg_indicators = ('Distinction', 'Merit', 'Pass')
    use_pg = any(any(ind in band['grade'] for ind in pg_indicators) for band in bands)

    if use_pg:
        main_grades = ["Distinction", "Merit", "Pass", "Fail"]
    else:
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
            grouped.setdefault(main_grade, []).append(band)
    
    return grouped