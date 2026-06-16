from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from core.utils.grade_bands import calculate_grade_bands
from .utils import build_marking_workbook, parse_builder_payload, validate_builder_config


def grade_bands_json(request):
    """AJAX endpoint returning default grade band calculated integers."""
    try:
        max_marks = int(request.GET.get("max_marks", 0))
        subdivision = request.GET.get("subdivision", "none")
        degree_level = request.GET.get("degree_level", "BEng")
        
        if max_marks < 1:
            return JsonResponse({"error": "Invalid max marks"}, status=400)
            
        bands = calculate_grade_bands(max_marks, subdivision, degree_level=degree_level)
        return JsonResponse({"bands": bands})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)



def builder(request):
    if request.method == "POST":
        from core.models import ThemeConfig
        theme = ThemeConfig.get_active()
        config = parse_builder_payload(request.POST.get("builder_payload"))
        config["theme_primary"] = theme.brand_primary
        config["theme_accent"] = theme.brand_accent
        errors = validate_builder_config(config)
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "marking_sheet_builder/builder.html",
                {
                    "default_boundaries": "\n".join(config["rubric_boundaries"]),
                    "initial_config": config,
                    "builder_errors": errors,
                },
            )
        workbook = build_marking_workbook(config)
        response = HttpResponse(
            workbook.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="marking_sheet_template.xlsx"'
        return response

    default_boundaries = "First\nUpper second\nLower second\nThird\nFail"
    messages.info(request, "Build a blank marking workbook and download it as an Excel template.")
    return render(
        request,
        "marking_sheet_builder/builder.html",
        {
            "default_boundaries": default_boundaries,
            "initial_config": {
                "name_mode": "full",
                "rows": 100,
                "max_mark": 100,
                "degree_level": "BEng",
                "rubric_boundaries": default_boundaries,
                "columns": [
                    {"type": "numeric", "title": "Numeric mark", "max_mark": 50},
                    {
                        "type": "rubric",
                        "title": "Rubric grade",
                        "max_mark": 50,
                        "subdivision": "none",
                    },
                    {"type": "feedback", "title": "Feedback"},
                ],
            },
        },
    )
