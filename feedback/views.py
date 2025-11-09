from django.shortcuts import render, redirect
from feedback.models import AssessmentTemplate

def home(request):
    return render(request, "feedback/home.html", {"page_title": "Feedback"})

def template_new(request):
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
    
    return render(request, "feedback/template_new.html")

def template_summary(request, pk):
    tpl = AssessmentTemplate.objects.get(pk=pk)
    return render(request, "feedback/template_summary.html", {"template": tpl})