import io
import re
import zipfile
import openpyxl
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
from django.utils.text import slugify

from core.utils.grade_bands import calculate_grade_bands, grade_for_percentage
from core.utils.charts import generate_radar_chart, generate_cohort_histogram
from core.utils.pdf_renderer import render_html_to_pdf


def build_pdf_layout_rows(layout):
    """
    Convert the flat layout list into a list of "rows" suitable for
    PDF table-cell rendering.

    Each row is a dict with:
      - 'type': 'full' | 'half-pair' | 'half-single'
      - 'blocks': list of 1 or 2 block dicts (only enabled blocks)

    Consecutive half-width enabled blocks are paired together.
    A lone half-width block (no following half) gets type 'half-single'.
    Full-width blocks always get their own row.
    """
    enabled = [b for b in layout if b.get("enabled")]
    rows = []
    i = 0
    while i < len(enabled):
        block = enabled[i]
        if block["width"] == "full":
            rows.append({"type": "full", "blocks": [block]})
            i += 1
        else:  # half
            # Look ahead for a second consecutive half block
            if i + 1 < len(enabled) and enabled[i + 1]["width"] == "half":
                rows.append({"type": "half-pair", "blocks": [block, enabled[i + 1]]})
                i += 2
            else:
                rows.append({"type": "half-single", "blocks": [block]})
                i += 1
    return rows


def upload_file(request):
    """
    Step 1: Upload View
    Accepts an uploaded grades spreadsheet, parses headers & rows in-memory using openpyxl,
    auto-infers columns and denominators, and saves them temporarily in session.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return render(request, "assessment_feedback/upload.html", {"error": "Please select a file to upload."})
        
        try:
            # Parse in-memory using openpyxl
            wb = openpyxl.load_workbook(uploaded_file, data_only=True)
            ws = wb.active
            
            # Extract rows
            rows = list(ws.iter_rows(values_only=True))
            if not rows or len(rows) < 2:
                return render(request, "assessment_feedback/upload.html", {"error": "The uploaded spreadsheet is empty."})
            
            # Extract headers (clean trailing/leading spaces)
            headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
            
            # Extract student rows (ignoring fully empty rows)
            data_rows = []
            for r in rows[1:]:
                if any(cell is not None for cell in r):
                    row_dict = {}
                    for idx, cell in enumerate(r):
                        if idx < len(headers):
                            row_dict[headers[idx]] = cell
                    data_rows.append(row_dict)
            
            # Auto-infer column roles
            inferred_mappings = {
                "col_student_name": "",
                "col_student_id": "",
                "categories": [],
                "degree_level": "BEng",  # default
                "subdivision": "none"    # default
            }
            
            # 1. Infer Name & ID
            for h in headers:
                hl = h.lower()
                # Fix: parenthesise correctly so both conditions check the guard
                if (("name" in hl or "student" in hl) and not inferred_mappings["col_student_name"]):
                    inferred_mappings["col_student_name"] = h
                elif (("id" in hl or "number" in hl or "code" in hl) and not inferred_mappings["col_student_id"]):
                    inferred_mappings["col_student_id"] = h
            
            # Fallback if names/ids not matched
            if not inferred_mappings["col_student_name"] and headers:
                inferred_mappings["col_student_name"] = headers[0]
            if not inferred_mappings["col_student_id"] and len(headers) > 1:
                inferred_mappings["col_student_id"] = headers[1]
                
            # Columns known to be non-category (text/comment columns)
            comment_keywords = ("comment", "feedback", "notes", "remarks", "text")

            # 2. Infer Categories & Comments
            # We look for numeric columns as category candidates
            candidate_categories = []
            for h in headers:
                if h == inferred_mappings["col_student_name"] or h == inferred_mappings["col_student_id"]:
                    continue

                # Skip columns that are clearly comment/text columns
                hl = h.lower()
                if any(kw in hl for kw in comment_keywords):
                    continue
                
                # Check if values in this column are predominantly numeric
                numeric_count = 0
                total_valid = 0
                for r in data_rows:
                    val = r.get(h)
                    if val is not None:
                        total_valid += 1
                        try:
                            float(val)
                            numeric_count += 1
                        except (ValueError, TypeError):
                            pass
                
                # If mostly numeric, it is a grading category!
                if total_valid > 0 and (numeric_count / total_valid) >= 0.7:
                    candidate_categories.append(h)

            
            # Build category configurations with max marks & comments mappings
            for cat in candidate_categories:
                # Infer max marks (denominator) from header (e.g. Design /30 or Design (30))
                max_marks = 100  # default fallback
                denom_match = re.search(r'/(\d+)', cat)
                if denom_match:
                    max_marks = int(denom_match.group(1))
                else:
                    # check maximum value in data
                    max_val = 0
                    for r in data_rows:
                        val = r.get(cat)
                        if val is not None:
                            try:
                                max_val = max(max_val, float(val))
                            except ValueError:
                                pass
                    if max_val > 0:
                        if max_val <= 10:
                            max_marks = 10
                        elif max_val <= 20:
                            max_marks = 20
                        elif max_val <= 30:
                            max_marks = 30
                        elif max_val <= 50:
                            max_marks = 50
                        else:
                            max_marks = 100
                
                # Infer weight from header (e.g. Design (30%))
                weight = None
                weight_match = re.search(r'\((\d+)%\)', cat)
                if weight_match:
                    weight = int(weight_match.group(1))
                
                # Find matching feedback comments column
                comments_col = ""
                cat_clean = re.sub(r'[/()%\d\s]+', '', cat).lower()  # e.g. "design"
                for h in headers:
                    hl = h.lower()
                    if h != cat and ("comment" in hl or "feedback" in hl) and cat_clean in hl:
                        comments_col = h
                        break
                
                inferred_mappings["categories"].append({
                    "column": cat,
                    "max_marks": max_marks,
                    "weight": weight,
                    "comments_column": comments_col,
                    "type": "numeric",      # Default category type
                    "subdivision": "none"   # Default subdivision
                })
            
            # Save parsed state inside session
            request.session["headers"] = headers
            request.session["uploaded_data"] = data_rows
            request.session["mappings"] = inferred_mappings
            request.session.modified = True
            
            return redirect("confirm_mappings")
            
        except Exception as e:
            return render(request, "assessment_feedback/upload.html", {"error": f"Failed to parse file: {str(e)}"})
            
    return render(request, "assessment_feedback/upload.html")


def confirm_mappings(request):
    """
    Step 2: Confirmation & Alignment Page
    Displays auto-inferred columns, rubric weightings, and bounds, allowing
    the academic to correct/adjust details before triggering generation.
    """
    headers = request.session.get("headers")
    mappings = request.session.get("mappings")
    uploaded_data = request.session.get("uploaded_data")
    
    if not headers or not mappings or not uploaded_data:
        return redirect("upload_file")
        
    if request.method == "POST":
        # Read student identifiers mapping
        mappings["col_student_name"] = request.POST.get("col_student_name")
        mappings["col_student_id"] = request.POST.get("col_student_id")
        mappings["degree_level"] = request.POST.get("degree_level", "BEng")
        mappings["subdivision"] = request.POST.get("subdivision", "none")
        
        # Read updated categories configs
        updated_categories = []
        for idx, cat_dict in enumerate(mappings["categories"]):
            col_name = cat_dict["column"]
            max_marks = int(request.POST.get(f"max_{idx}", 100))
            weight = request.POST.get(f"weight_{idx}")
            comments_col = request.POST.get(f"comments_{idx}")
            cat_type = request.POST.get(f"type_{idx}", "numeric")
            
            updated_categories.append({
                "column": col_name,
                "max_marks": max_marks,
                "weight": int(weight) if weight else None,
                "comments_column": comments_col,
                "type": cat_type,
                "subdivision": mappings["subdivision"]
            })
            
        mappings["categories"] = updated_categories
        request.session["mappings"] = mappings
        request.session.modified = True
        
        return redirect("configure_layout")
        
    return render(request, "assessment_feedback/confirm.html", {
        "headers": headers,
        "mappings": mappings,
        "sample_rows": uploaded_data[:3]
    })


def configure_layout(request):
    """
    Step 2.5: PDF Layout Builder Configuration Page
    Allows academics to add/remove content blocks, control their positioning (ordering),
    and set their grid widths (half vs. full).
    """
    headers = request.session.get("headers")
    mappings = request.session.get("mappings")
    uploaded_data = request.session.get("uploaded_data")
    
    if not headers or not mappings or not uploaded_data:
        return redirect("upload_file")
        
    default_layout = [
        {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
        {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True},
        {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True},
        {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": True},
    ]
    layout = request.session.get("layout", default_layout)
    
    if request.method == "POST":
        block_order = request.POST.get("block_order", "").split(",")
        if not any(block_order):
            block_order = [b["id"] for b in default_layout]
            
        updated_layout = []
        name_map = {
            "category_marks": "Category Marks",
            "feedback": "Feedback Comments",
            "radar_chart": "Radar Chart",
            "histogram": "Histogram Chart",
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
            request.session["layout"] = updated_layout
            request.session.modified = True
            
        return redirect("process_feedback")
        
    return render(request, "assessment_feedback/configure_layout.html", {
        "layout": layout
    })


def process_feedback(request):
    """
    Step 3: Processing & PDF ZIP Stream
    Computes cohort stats (averages, final score arrays), loops over student rows to
    generate custom Matplotlib radar/hist charts, renders WeasyPrint PDFs in-memory,
    and returns a downloadable ZIP archive with zero data persistence.
    """
    uploaded_data = request.session.get("uploaded_data")
    mappings = request.session.get("mappings")
    
    if not uploaded_data or not mappings:
        return redirect("upload_file")
        
    layout = request.session.get("layout")
    if not layout:
        layout = [
            {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
            {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True},
            {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True},
            {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": True},
        ]
        
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    degree_level = mappings["degree_level"]
    subdivision = mappings["subdivision"]
    categories = mappings["categories"]
    
    # Calculate Cohort Statistics
    cohort_final_marks = []
    category_cohort_marks = {cat["column"]: [] for cat in categories}
    
    for r in uploaded_data:
        student_total = 0
        for cat in categories:
            col = cat["column"]
            val = r.get(col, 0)
            try:
                mark_val = float(val) if val is not None else 0
            except ValueError:
                mark_val = 0
            category_cohort_marks[col].append(mark_val)
            student_total += mark_val
        cohort_final_marks.append(student_total)
        
    # Class averages per category
    category_averages = {}
    for cat in categories:
        col = cat["column"]
        vals = category_cohort_marks[col]
        category_averages[col] = sum(vals) / len(vals) if vals else 0
        
    # Calculate Max Possible Marks across all active categories
    total_max_marks = sum(cat["max_marks"] for cat in categories)
    
    # In-memory ZIP buffer
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, student_row in enumerate(uploaded_data):
            student_name = str(student_row.get(col_name, f"Student {idx+1}")).strip()
            student_id = str(student_row.get(col_id, f"ID-{idx+1}")).strip()
            
            # Skip empty entries
            if not student_name and not student_id:
                continue
                
            student_total_score = 0
            student_categories_data = []
            
            # Prepare data and percentages for student's radar chart
            radar_labels = []
            student_radar_percentages = []
            avg_radar_percentages = []
            
            for cat in categories:
                col = cat["column"]
                max_marks = cat["max_marks"]
                raw_mark = student_row.get(col, 0)
                try:
                    mark_val = float(raw_mark) if raw_mark is not None else 0
                except ValueError:
                    mark_val = 0
                    
                student_total_score += mark_val
                
                # Percentages for Radar
                student_pct = (mark_val / max_marks) * 100 if max_marks > 0 else 0
                avg_pct = (category_averages[col] / max_marks) * 100 if max_marks > 0 else 0
                
                radar_labels.append(col)
                student_radar_percentages.append(student_pct)
                avg_radar_percentages.append(avg_pct)
                
                # Grade Calculations
                grade_awarded = None
                if cat["type"] == "grade" and max_marks > 0:
                    bands = calculate_grade_bands(max_marks, subdivision, degree_level=degree_level)
                    # Match score to closest grade band
                    closest_band = min(bands, key=lambda b: abs(b["marks"] - mark_val))
                    grade_awarded = closest_band["grade"]
                
                student_categories_data.append({
                    "label": col,
                    "mark": mark_val,
                    "max_marks": max_marks,
                    "grade_awarded": grade_awarded,
                    "feedback_comment": student_row.get(cat["comments_column"], ""),
                    "is_grade": cat["type"] == "grade"
                })
                
            # Derive overall assessment grade
            overall_pct = (student_total_score / total_max_marks) * 100 if total_max_marks > 0 else 0
            overall_grade = grade_for_percentage(overall_pct)
            
            # Generate SVGs and base64-encode them
            radar_svg = generate_radar_chart(radar_labels, student_radar_percentages, avg_radar_percentages)
            hist_svg = generate_cohort_histogram(cohort_final_marks, student_total_score, max_score=total_max_marks, subdivision=subdivision)
            
            import base64
            radar_base64 = base64.b64encode(radar_svg.encode('utf-8')).decode('utf-8')
            hist_base64 = base64.b64encode(hist_svg.encode('utf-8')).decode('utf-8')
            
            # Render HTML to PDF template
            context = {
                "student_name": student_name,
                "student_id": student_id,
                "categories": student_categories_data,
                "total_score": student_total_score,
                "total_max_marks": total_max_marks,
                "overall_grade": overall_grade,
                "radar_base64": radar_base64,
                "hist_base64": hist_base64,
                "degree_level": degree_level,
                "layout": layout,
                "layout_rows": build_pdf_layout_rows(layout),
            }
            
            # Render PDF in-memory using WeasyPrint
            html_content = render_html_to_pdf_template(request, context)
            pdf_bytes = render_html_to_pdf(html_content)
            
            # Add to ZIP archive
            filename = f"{slugify(student_id)}_{slugify(student_name)}.pdf"
            zip_file.writestr(filename, pdf_bytes)
            
    # Send ZIP file response
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=student_feedback_reports.zip"
    return response


def render_html_to_pdf_template(request, context):
    """
    Renders the beautiful glassmorphic feedback sheet directly
    to a compiled raw HTML string in context.
    """
    return render_to_string("assessment_feedback/feedback_pdf.html", context, request=request)
