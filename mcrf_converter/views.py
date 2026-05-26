from django.shortcuts import render


def converter_page(request):
    """
    Renders the Gradebook / MCRF Merger client-side HTML application.
    Executes entirely in-browser via SheetJS to preserve GDPR zero-storage data policy.
    """
    return render(request, "mcrf_converter/gradebook_file_merge.html")
