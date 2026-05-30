from django.shortcuts import render


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
    ]
    return render(request, "core/home.html", {"tools": tools})
