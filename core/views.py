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
            "description": "Generate module summary sheets from a completed module marks spreadsheet.",
            "url_name": "module_upload",
            "cta": "Create module summaries",
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
            "title": "MCRF Converter",
            "description": "Merge and convert gradebook files into a format ready for module workflows.",
            "url_name": "mcrf_converter",
            "cta": "Convert gradebook files",
        },
    ]
    return render(request, "core/home.html", {"tools": tools})
