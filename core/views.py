from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ThemeConfig


def portal_home(request):
    tools = [
        {
            "title": "Assessment Feedback",
            "description": "Generate individual student feedback sheets from an uploaded marking spreadsheet.",
            "url_name": "upload_file",
            "cta": "Create feedback sheets",
        },
        {
            "title": "Module Summary",
            "description": "Generate module summary sheets from a completed MCRF spreadsheet.",
            "url_name": "module_upload",
            "cta": "Create module summaries",
        },
        {
            "title": "Cohort Summary Report",
            "description": "Generate dynamic cohort summary reports from a completed MCRF spreadsheet.",
            "url_name": "cohort_report_upload",
            "cta": "Create cohort report",
        },
        {
            "title": "Rubric Generator",
            "description": "Build reusable marking templates, rubric bands, and feedback sheet layouts.",
            "url_name": "rubric_home",
            "cta": "Manage templates",
        },
        {
            "title": "Comments Generator",
            "description": "Prepare reusable structured comments for exam and assessment feedback.",
            "url_name": "index",
            "cta": "Build comments",
        },
        {
            "title": "Marking Sheet Converters",
            "description": "Merge gradebooks and populate MCRF templates dynamically.",
            "url_name": "marking_converters",
            "cta": "Convert and populate",
        },
        {
            "title": "Marking Sheet Builder",
            "description": "Build a blank assessment marking spreadsheet with marks, rubric dropdowns, notes, and feedback columns.",
            "url_name": "marking_sheet_builder",
            "cta": "Create marking template",
        },
        {
            "title": "Programme Analytics",
            "description": "Aggregate and compare performance metrics across multiple modules and cohorts.",
            "url_name": "analytics_upload",
            "cta": "Analyse programme",
        },
    ]
    return render(request, "core/home.html", {"tools": tools})


def theme_settings(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            name = request.POST.get("name", "").strip() or "Unnamed Theme"
            ThemeConfig.objects.create(
                name=name,
                brand_primary=request.POST.get("brand_primary", "#1a1a2e"),
                brand_primary_dark=request.POST.get("brand_primary_dark", "#0f172a"),
                brand_primary_light=request.POST.get("brand_primary_light", "#2e2e4a"),
                brand_accent=request.POST.get("brand_accent", "#c8a951"),
                is_active=False
            )
            messages.success(request, f"Theme '{name}' created successfully!")
        elif action == "edit":
            theme_id = request.POST.get("theme_id")
            theme = get_object_or_404(ThemeConfig, pk=theme_id)
            theme.name = request.POST.get("name", "").strip() or theme.name
            theme.brand_primary = request.POST.get("brand_primary", "#1a1a2e")
            theme.brand_primary_dark = request.POST.get("brand_primary_dark", "#0f172a")
            theme.brand_primary_light = request.POST.get("brand_primary_light", "#2e2e4a")
            theme.brand_accent = request.POST.get("brand_accent", "#c8a951")
            theme.save()
            messages.success(request, f"Theme '{theme.name}' updated successfully!")
        elif action == "activate":
            theme_id = request.POST.get("theme_id")
            theme = get_object_or_404(ThemeConfig, pk=theme_id)
            theme.is_active = True
            theme.save()
            messages.success(request, f"Theme '{theme.name}' is now active!")
        elif action == "deactivate":
            ThemeConfig.objects.update(is_active=False)
            messages.success(request, "All custom themes deactivated. Portal returned to default theme.")
        elif action == "delete":
            theme_id = request.POST.get("theme_id")
            theme = get_object_or_404(ThemeConfig, pk=theme_id)
            theme_name = theme.name
            theme.delete()
            messages.success(request, f"Theme '{theme_name}' deleted successfully.")
        
        return redirect("theme_settings")
        
    themes = ThemeConfig.objects.all().order_by("name")
    active_theme = ThemeConfig.get_active()
    has_custom_active = ThemeConfig.objects.filter(is_active=True).exists()
    
    return render(
        request,
        "core/theme_settings.html",
        {
            "themes": themes,
            "active_theme": active_theme,
            "has_custom_active": has_custom_active,
        }
    )
