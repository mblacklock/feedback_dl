import io
import re
import zipfile
import base64
import openpyxl
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.utils.text import slugify

from core.utils.grade_bands import calculate_grade_bands, grade_for_percentage
from core.utils.charts import generate_cohort_histogram
from assessment_feedback.views import build_feedback_sheet_layout_rows


def normalize_student_id(id_val):
    """
    Normalizes a student number to resolve format variations (prefixes like 'w', suffixes like '/1').
    Extracts the longest sequence of digits of length >= 5.
    """
    if id_val is None:
        return ""
    s = str(id_val).strip().lower()
    matches = re.findall(r'\d+', s)
    if matches:
        # Sort by length descending to get the longest digit sequence
        matches.sort(key=len, reverse=True)
        longest = matches[0]
        if len(longest) >= 5:
            return longest
    return re.sub(r'[^a-z0-9]', '', s)


def round_mark_pct(val):
    """
    Rounds a percentage mark to the nearest integer.
    Any value whose integer part ends in 9 (e.g. 39.x, 59.x) is rounded up
    to the next decade (40, 60, etc.) per module reporting conventions.
    """
    rounded = round(val)
    if rounded % 10 == 9:
        rounded += 1
    return rounded


def parse_non_negative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def parse_mcrf_workbook(file_file):
    """
    Parses a spreadsheet in-memory. Detects MCRF signature block
    and dynamically merges multi-row headings for clarity (e.g. "CW1" + "Mark" -> "CW1 - Mark").
    Supports modern .xlsx (via openpyxl) and legacy .xls (via xlrd).
    """
    file_bytes = file_file.read()
    file_file.seek(0)
    
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        try:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file_bytes)
            ws = wb.sheet_by_index(0)
            rows = [ws.row_values(i) for i in range(ws.nrows)]
        except Exception as e:
            raise ValueError(f"Spreadsheet format not recognized or corrupted: {str(e)}")
            
    if not rows or len(rows) < 2:
        raise ValueError("The uploaded spreadsheet is empty.")
        
    is_mcrf = False
    header_row_idx = 0
    
    # Scan first 50 rows to detect MCRF signatures and find the main header row
    for i in range(min(len(rows), 50)):
        row_cells = [str(c).strip() if c is not None else "" for c in rows[i]]
        row_text = " ".join(row_cells).lower()
        if "module marks record form" in row_text or "(mcrf)" in row_text:
            is_mcrf = True
            
        if any(keyword in cell.lower() for cell in row_cells for keyword in ["student id", "student no", "student number", "username"]):
            header_row_idx = i
            break
            
    raw_headers = [str(c).strip() if c is not None else "" for c in rows[header_row_idx]]
    headers = list(raw_headers)
    
    # Replace empty headers with '<Column X>'
    from openpyxl.utils import get_column_letter
    for idx in range(len(headers)):
        if not headers[idx]:
            headers[idx] = f"<Column {get_column_letter(idx + 1)}>"
            
    # If MCRF, merge parent and child headers
    if is_mcrf and header_row_idx > 0:
        parent_row = [str(c).strip() if c is not None else "" for c in rows[header_row_idx - 1]]
        current_parent = ""
        for c in range(len(headers)):
            p_val = parent_row[c] if c < len(parent_row) else ""
            if p_val != "":
                current_parent = p_val
                
            m_val = raw_headers[c] # Use raw header to verify original contents
            m_val_lower = m_val.lower()
            if m_val != "" and current_parent != "" and current_parent != m_val:
                if any(k in m_val_lower for k in ["mark", "grad", "result", "score"]):
                    headers[c] = f"{current_parent} - {m_val}"
                    
    # Read rows
    data_rows = []
    for r in rows[header_row_idx + 1:]:
        if any(cell is not None for cell in r):
            row_dict = {}
            for idx, cell in enumerate(r):
                if idx < len(headers):
                    h_name = headers[idx]
                    if h_name:
                        row_dict[h_name] = cell
            data_rows.append(row_dict)

    # --- Module details detection ---
    # Try C7 first (row 6, col 2) — the standard MCRF cell for module info.
    # If that's empty, scan pre-header rows for any cell matching a module code pattern.
    module_code = ""
    module_title = ""
    MODULE_CODE_RE = re.compile(r'^([A-Z]{2,6}\d{3,5}[A-Z]?)\s*[-:–]?\s*(.*)$')

    def _try_parse_module_cell(val):
        """Return (code, title) if val looks like a module details cell, else ('', '')."""
        if not val:
            return "", ""
        text = str(val).strip()
        m = MODULE_CODE_RE.match(text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return "", ""

    # 1. Try canonical MCRF position: row 7 (index 6), column C (index 2)
    if len(rows) > 6:
        c7_val = rows[6][2] if len(rows[6]) > 2 else None
        module_code, module_title = _try_parse_module_cell(c7_val)

    # 2. If not found, scan all pre-header rows for a matching cell
    if not module_code:
        for row in rows[:header_row_idx]:
            for cell in row:
                code, title = _try_parse_module_cell(cell)
                if code:
                    module_code, module_title = code, title
                    break
            if module_code:
                break

    return headers, data_rows, is_mcrf, {"module_code": module_code, "module_title": module_title}


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
                hl = h.lower()
                # Exclude columns representing overall results, averages, or student identifiers
                if h == inferred_mappings["col_student_name"] or h == inferred_mappings["col_student_id"]:
                    continue
                if "total" in hl or "overall" in hl or "average" in hl or "final" in hl or "module" in hl:
                    continue
                    
                # Match ONLY columns containing "mark" (ignoring grade columns)
                if "mark" in hl:
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
        {"id": "assessment_table", "name": "Assessment Breakdown Table", "width": "half", "enabled": True},
        {"id": "comparison_chart", "name": "Comparative Visual Chart", "width": "half", "enabled": True},
        {"id": "overall_card", "name": "Weighted Final Module Score Card", "width": "full", "enabled": True},
    ]
    layout = request.session.get("module_layout", default_layout)
    
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
                    
                updated_layout.append({
                    "id": bid,
                    "name": name_map[bid],
                    "width": width,
                    "enabled": enabled
                })
                
        if updated_layout:
            request.session["module_layout"] = updated_layout
            request.session.modified = True
            
        return redirect("module_process")
        
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    subdivision = mappings["subdivision"]
    components = mappings["components"]
    
    # Calculate all cohort weighted final percentages for the histogram
    cohort_weighted_finals = []
    for r in uploaded_data:
        row_weighted_pct = 0
        for comp in components:
            col = comp["column"]
            max_marks = comp["max_marks"]
            weight = comp["weight"]
            val = r.get(col, 0)
            try:
                mark_val = float(val) if val is not None else 0
            except ValueError:
                mark_val = 0
            pct = (mark_val / max_marks) * 100 if max_marks > 0 else 0
            row_weighted_pct += (pct * weight) / 100
        cohort_weighted_finals.append(row_weighted_pct)
        
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
        student_name = str(student_row.get(col_name, f"Student {preview_student_index+1}")).strip()
        student_id = str(student_row.get(col_id, f"ID-{preview_student_index+1}")).strip()
        
        student_components_data = []
        weighted_final_pct = 0
        
        for comp in components:
            col = comp["column"]
            max_marks = comp["max_marks"]
            weight = comp["weight"]
            raw_mark = student_row.get(col, 0)
            try:
                mark_val = float(raw_mark) if raw_mark is not None else 0
            except ValueError:
                mark_val = 0
                
            pct_awarded = (mark_val / max_marks) * 100 if max_marks > 0 else 0
            weighted_final_pct += (pct_awarded * weight) / 100
            
            pct_awarded_rounded = round_mark_pct(pct_awarded)
            comp_grade = grade_for_percentage(pct_awarded)
            label_short = col.split(" - ")[0] if " - " in col else col
            
            student_components_data.append({
                "label": col,
                "label_short": label_short,
                "percentage": pct_awarded_rounded,
                "weight": weight,
                "grade": comp_grade
            })
            
        weighted_final_pct_rounded = round_mark_pct(weighted_final_pct)
        overall_grade = grade_for_percentage(weighted_final_pct)
        chart_svg = generate_cohort_histogram(cohort_weighted_finals, weighted_final_pct_rounded)
        chart_base64 = base64.b64encode(chart_svg.encode('utf-8')).decode('utf-8') if chart_svg else ""
        
        preview_student = {
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
    subdivision = mappings["subdivision"]
    components = mappings["components"]
    
    # Pre-compute all cohort weighted final percentages for the histogram
    cohort_weighted_finals = []
    for r in uploaded_data:
        row_weighted_pct = 0
        for comp in components:
            col = comp["column"]
            max_marks = comp["max_marks"]
            weight = comp["weight"]
            val = r.get(col, 0)
            try:
                mark_val = float(val) if val is not None else 0
            except ValueError:
                mark_val = 0
            pct = (mark_val / max_marks) * 100 if max_marks > 0 else 0
            row_weighted_pct += (pct * weight) / 100
        cohort_weighted_finals.append(row_weighted_pct)
        
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, student_row in enumerate(uploaded_data):
            student_name = str(student_row.get(col_name, f"Student {idx+1}")).strip()
            raw_student_id = str(student_row.get(col_id, f"ID-{idx+1}")).strip()
            student_id = normalize_student_id(raw_student_id)
            
            if not student_name and not student_id:
                continue
                
            student_components_data = []
            weighted_final_pct = 0
            
            for comp in components:
                col = comp["column"]
                max_marks = comp["max_marks"]
                weight = comp["weight"]
                raw_mark = student_row.get(col, 0)
                try:
                    mark_val = float(raw_mark) if raw_mark is not None else 0
                except ValueError:
                    mark_val = 0
                    
                pct_awarded = (mark_val / max_marks) * 100 if max_marks > 0 else 0
                weighted_final_pct += (pct_awarded * weight) / 100
                
                pct_awarded_rounded = round_mark_pct(pct_awarded)
                comp_grade = grade_for_percentage(pct_awarded)
                label_short = col.split(" - ")[0] if " - " in col else col
                
                student_components_data.append({
                    "label": col,
                    "label_short": label_short,
                    "percentage": pct_awarded_rounded,
                    "weight": weight,
                    "grade": comp_grade
                })
                
            # Derive overall weighted module grade
            weighted_final_pct_rounded = round_mark_pct(weighted_final_pct)
            overall_grade = grade_for_percentage(weighted_final_pct)
            
            # Generate Base64 Cohort Distribution Histogram SVG
            chart_svg = generate_cohort_histogram(cohort_weighted_finals, weighted_final_pct_rounded)
            chart_base64 = base64.b64encode(chart_svg.encode('utf-8')).decode('utf-8') if chart_svg else ""
            
            context = {
                "student_name": student_name,
                "student_id": student_id,
                "components": student_components_data,
                "weighted_final_pct": weighted_final_pct_rounded,
                "overall_grade": overall_grade,
                "chart_base64": chart_base64,
                "layout": layout,
                "layout_rows": build_feedback_sheet_layout_rows(layout),
                "module_code": mappings.get("module_code", "COMP101"),
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
