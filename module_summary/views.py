import io
import re
import zipfile
import base64
import openpyxl
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils.text import slugify

from core.utils.grade_bands import calculate_grade_bands, grade_for_percentage
from core.utils.charts import generate_cohort_histogram
from assessment_feedback.views import build_feedback_sheet_layout_rows
from core.mcrf_parser import parse_mcrf_workbook, is_assessment_component_column


from core.utils.student_id import format_student_id
from core.utils.marks import (
    module_numeric_mark,
    component_percentage,
    round_mark_pct,
    build_module_cohort_weighted_finals
)


def normalize_student_id(id_val):
    """
    Normalizes a student number to resolve format variations (prefixes like 'w', suffixes like '/1').
    Uses format_student_id to format to 'w12345678' if there is an 8-digit sequence.
    Otherwise, extracts the longest sequence of digits of length >= 5.
    """
    if id_val is None:
        return ""
        
    formatted = format_student_id(id_val)
    if formatted.startswith('w') and len(formatted) == 9 and formatted[1:].isdigit():
        return formatted

    s = str(id_val).strip().lower()
    matches = re.findall(r'\d+', s)
    if matches:
        # Sort by length descending to get the longest digit sequence
        matches.sort(key=len, reverse=True)
        longest = matches[0]
        if len(longest) >= 5:
            return longest
    return re.sub(r'[^a-z0-9]', '', s)



def parse_non_negative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None



def build_module_student_context(student_row, student_index, mappings, cohort_weighted_finals, normalize_id=False):
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    components = mappings["components"]

    student_name = str(student_row.get(col_name, f"Student {student_index+1}")).strip()
    raw_student_id = str(student_row.get(col_id, f"ID-{student_index+1}")).strip()
    student_id = normalize_student_id(raw_student_id) if normalize_id else raw_student_id
    student_components_data = []
    weighted_final_pct = 0

    for comp in components:
        col = comp["column"]
        pct_awarded = component_percentage(student_row, comp)
        weighted_final_pct += (pct_awarded * comp["weight"]) / 100
        label_short = col.split(" - ")[0] if " - " in col else col

        student_components_data.append({
            "label": col,
            "label_short": label_short,
            "percentage": round_mark_pct(pct_awarded),
            "weight": comp["weight"],
            "grade": grade_for_percentage(pct_awarded),
        })

    weighted_final_pct_rounded = round_mark_pct(weighted_final_pct)
    overall_grade = grade_for_percentage(weighted_final_pct)
    chart_svg = generate_cohort_histogram(cohort_weighted_finals, weighted_final_pct_rounded)
    chart_base64 = base64.b64encode(chart_svg.encode("utf-8")).decode("utf-8") if chart_svg else ""

    return {
        "student_name": student_name,
        "student_id": student_id,
        "components": student_components_data,
        "weighted_final_pct": weighted_final_pct_rounded,
        "overall_grade": overall_grade,
        "chart_base64": chart_base64,
        "total_score": weighted_final_pct_rounded,
        "overall_percentage": weighted_final_pct_rounded,
        "module_code": mappings.get("module_code", "COMP101"),
        "module_title": mappings.get("module_title", "Module Summary"),
    }

def upload_mcrf(request):
    """
    Step 1: Upload View
    Accepts a single completed MCRF spreadsheet, parses it in-memory,
    auto-infers columns, and saves data to session.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return render(request, "module_summary/upload.html", {"error": "Please select a file to upload."})
            
        try:
            headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(uploaded_file)
            
            inferred_mappings = {
                "col_student_name": "",
                "col_student_id": "",
                "components": [],
                "degree_level": "BEng",
                "subdivision": "none",
                "module_code": module_info.get("module_code", ""),
                "module_title": module_info.get("module_title", ""),
            }
            
            # Infern Name & Student ID
            for h in headers:
                hl = h.lower()
                if ("name" in hl or "student" in hl) and not inferred_mappings["col_student_name"] and "id" not in hl and "no" not in hl:
                    inferred_mappings["col_student_name"] = h
                elif ("id" in hl or "number" in hl or "no" in hl or "username" in hl) and not inferred_mappings["col_student_id"]:
                    inferred_mappings["col_student_id"] = h
                    
            if not inferred_mappings["col_student_name"] and len(headers) > 1:
                inferred_mappings["col_student_name"] = headers[1]  # Default: Column B
            if not inferred_mappings["col_student_id"] and len(headers) > 1:
                inferred_mappings["col_student_id"] = headers[1]
                
            # Infer Component Mark Columns (e.g. "CW1 - Mark", "Exam - Mark")
            for h in headers:
                # Exclude columns representing student identifiers
                if h == inferred_mappings["col_student_name"] or h == inferred_mappings["col_student_id"]:
                    continue
                if is_assessment_component_column(h):
                    inferred_mappings["components"].append({
                        "column": h,
                        "max_marks": 100,  # Each component is always out of 100
                        "weight": 0,
                        "type": "numeric"  # Always numeric, no rubric grades
                    })
                    
            # Check if any component has an explicit weight defined in the header
            has_explicit_weights = False
            for comp in inferred_mappings["components"]:
                weight_match = re.search(r'(\d+)\s*%', comp["column"])
                if weight_match:
                    comp["weight"] = int(weight_match.group(1))
                    has_explicit_weights = True
                    
            # If no explicit weights are found in any component, split evenly to sum to 100
            if not has_explicit_weights:
                num_comps = len(inferred_mappings["components"])
                if num_comps > 0:
                    even_weight = 100 // num_comps
                    for idx, comp in enumerate(inferred_mappings["components"]):
                        # Handle rounding adjustments in the last element
                        if idx == num_comps - 1:
                            comp["weight"] = 100 - (even_weight * (num_comps - 1))
                        else:
                            comp["weight"] = even_weight

            if not inferred_mappings["components"]:
                return render(request, "module_summary/upload.html", {
                    "error": "No component mark columns were detected. Please upload an MCRF with columns containing component marks."
                })
                        
            request.session["module_headers"] = headers
            request.session["module_uploaded_data"] = data_rows
            request.session["module_mappings"] = inferred_mappings
            request.session.modified = True
            
            return redirect("module_confirm")
            
        except Exception as e:
            return render(request, "module_summary/upload.html", {"error": f"Failed to parse MCRF file: {str(e)}"})
            
    return render(request, "module_summary/upload.html")


def confirm_module_mappings(request):
    """
    Step 2: Alignment View
    Academics verify column selections, set component weights (must sum to 100), and verify subdivisions.
    """
    headers = request.session.get("module_headers")
    mappings = request.session.get("module_mappings")
    uploaded_data = request.session.get("module_uploaded_data")
    
    if not headers or not mappings or not uploaded_data:
        return redirect("module_upload")

    if not mappings.get("components"):
        return render(request, "module_summary/confirm.html", {
            "headers": headers,
            "mappings": mappings,
            "sample_rows": uploaded_data[:3],
            "error": "No component mark columns were detected.",
        })
        
    error = None
    if request.method == "POST":
        mappings["col_student_name"] = request.POST.get("col_student_name")
        mappings["col_student_id"] = request.POST.get("col_student_id")
        mappings["module_code"] = request.POST.get("module_code", "").strip()
        mappings["module_title"] = request.POST.get("module_title", "").strip()
        mappings["degree_level"] = "BEng"
        mappings["subdivision"] = "none"
        
        # Read components
        updated_comps = []
        total_weight = 0
        
        for idx, comp_dict in enumerate(mappings["components"]):
            col_name = comp_dict["column"]
            weight = parse_non_negative_int(request.POST.get(f"weight_{idx}"))
            if weight is None:
                error = f"Weight for {col_name} must be a whole number between 0 and 100."
                return render(request, "module_summary/confirm.html", {
                    "headers": headers,
                    "mappings": mappings,
                    "sample_rows": uploaded_data[:3],
                    "error": error,
                })
            if weight > 100:
                error = f"Weight for {col_name} must be a whole number between 0 and 100."
                return render(request, "module_summary/confirm.html", {
                    "headers": headers,
                    "mappings": mappings,
                    "sample_rows": uploaded_data[:3],
                    "error": error,
                })
            
            total_weight += weight
            updated_comps.append({
                "column": col_name,
                "max_marks": 100,  # Each component is always out of 100
                "weight": weight,
                "type": "numeric"
            })
            
        mappings["components"] = updated_comps
        request.session["module_mappings"] = mappings
        request.session.modified = True
        
        # Enforce weight sum validation
        if total_weight != 100:
            error = f"Total component weight must sum to exactly 100% (currently {total_weight}%)."
        else:
            return redirect("module_layout")
            
    return render(request, "module_summary/confirm.html", {
        "headers": headers,
        "mappings": mappings,
        "sample_rows": uploaded_data[:3],
        "error": error
    })


def configure_module_layout(request):
    """
    Step 2.5: Interactive WYSIWYG Layout Editor for Module Summary sheets.
    """
    uploaded_data = request.session.get("module_uploaded_data")
    mappings = request.session.get("module_mappings")
    
    if not uploaded_data or not mappings:
        return redirect("module_upload")
        
    default_layout = [
        {"id": "assessment_table", "name": "Assessment Breakdown Table", "width": "half", "enabled": True, "own_row": False},
        {"id": "comparison_chart", "name": "Comparative Visual Chart", "width": "half", "enabled": True, "own_row": False},
        {"id": "overall_card", "name": "Weighted Final Module Score Card", "width": "full", "enabled": True, "own_row": False},
    ]
    layout = request.session.get("module_layout", default_layout)
    
    # Ensure all layout blocks have 'own_row' defined
    modified_layout = False
    for b in layout:
        if "own_row" not in b:
            b["own_row"] = False
            modified_layout = True
    if modified_layout:
        request.session["module_layout"] = layout
        request.session.modified = True
    
    if request.method == "POST":
        block_order = request.POST.get("block_order", "").split(",")
        if not any(block_order):
            block_order = [b["id"] for b in default_layout]
            
        updated_layout = []
        name_map = {
            "assessment_table": "Assessment Breakdown Table",
            "overall_card": "Weighted Final Module Score Card",
            "comparison_chart": "Comparative Visual Chart",
        }
        
        for bid in block_order:
            bid = bid.strip()
            if bid in name_map:
                enabled = request.POST.get(f"enabled_{bid}") == "true"
                width = request.POST.get(f"width_{bid}", "full")
                if width not in ["half", "full"]:
                    width = "full"
                own_row = request.POST.get(f"own_row_{bid}") == "true"
                    
                updated_layout.append({
                    "id": bid,
                    "name": name_map[bid],
                    "width": width,
                    "enabled": enabled,
                    "own_row": own_row
                })
                
        if updated_layout:
            request.session["module_layout"] = updated_layout
            request.session.modified = True
            
        return redirect("module_process")
        
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    components = mappings["components"]
    
    cohort_weighted_finals = build_module_cohort_weighted_finals(uploaded_data, components)
        
    # Prepare student selection list
    students_list = []
    for idx, r in enumerate(uploaded_data):
        s_name = str(r.get(col_name, f"Student {idx+1}")).strip()
        s_id = str(r.get(col_id, f"ID-{idx+1}")).strip()
        if s_name or s_id:
            students_list.append({
                "index": idx,
                "name": s_name,
                "id": s_id,
            })
            
    # Read selected student index from query param
    try:
        preview_student_index = int(request.GET.get("student_index", 0))
        if preview_student_index < 0 or preview_student_index >= len(uploaded_data):
            preview_student_index = 0
    except (ValueError, TypeError):
        preview_student_index = 0
        
    preview_student = None
    if uploaded_data:
        student_row = uploaded_data[preview_student_index]
        preview_student = build_module_student_context(
            student_row,
            preview_student_index,
            mappings,
            cohort_weighted_finals,
        )
        
    return render(request, "module_summary/configure_layout.html", {
        "layout": layout,
        "preview_student_index": preview_student_index,
        "students_list": students_list,
        "preview_student": preview_student,
    })


def process_module_summary(request):
    """
    Step 3: HTML Generation & ZIP Download View
    Calculates weighted marks, generates side-by-side comparison bar charts,
    and returns a downloadable ZIP of self-contained summary HTML sheets.
    """
    uploaded_data = request.session.get("module_uploaded_data")
    mappings = request.session.get("module_mappings")
    
    if not uploaded_data or not mappings:
        return redirect("module_upload")
        
    default_layout = [
        {"id": "assessment_table", "name": "Assessment Breakdown Table", "width": "half", "enabled": True},
        {"id": "comparison_chart", "name": "Comparative Visual Chart", "width": "half", "enabled": True},
        {"id": "overall_card", "name": "Weighted Final Module Score Card", "width": "full", "enabled": True},
    ]
    layout = request.session.get("module_layout", default_layout)
    
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    components = mappings["components"]
    
    cohort_weighted_finals = build_module_cohort_weighted_finals(uploaded_data, components)
        
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, student_row in enumerate(uploaded_data):
            student_name = str(student_row.get(col_name, f"Student {idx+1}")).strip()
            raw_student_id = str(student_row.get(col_id, f"ID-{idx+1}")).strip()
            student_id = normalize_student_id(raw_student_id)
            
            if not student_name and not student_id:
                continue

            student_context = build_module_student_context(
                student_row,
                idx,
                mappings,
                cohort_weighted_finals,
                normalize_id=True,
            )
            context = {
                **student_context,
                "layout": layout,
                "layout_rows": build_feedback_sheet_layout_rows(layout),
                "module_title": mappings.get("module_title", "Module Performance"),
            }
            
            # Render HTML to String
            from django.template.loader import render_to_string
            html_content = render_to_string("module_summary/summary_sheet.html", context, request=request)
            
            filename = f"module_summary_{slugify(student_id)}_{slugify(student_name)}.html"
            zip_file.writestr(filename, html_content.encode('utf-8'))
            
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=module_summary_reports.zip"
    return response
