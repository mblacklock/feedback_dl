from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render

from .utils import build_marking_workbook, parse_builder_payload, validate_builder_config


def builder(request):
    if request.method == "POST":
        config = parse_builder_payload(request.POST.get("builder_payload"))
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
