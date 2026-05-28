import io
import re
import zipfile
import base64
import openpyxl
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.text import slugify

from core.utils.grade_bands import calculate_grade_bands
from core.utils.charts import generate_radar_chart, generate_cohort_histogram



def grade_for_percentage_and_degree(percentage, degree_level=None):
    if is_m_level_degree(degree_level):
        if percentage >= 70:
            return "1st/Dist"
        elif percentage >= 60:
            return "2:1/Merit"
        elif percentage >= 50:
            return "2:2/Pass"
        else:
            return "Fail"
    else:
        if percentage >= 70:
            return "1st"
        elif percentage >= 60:
            return "2:1"
        elif percentage >= 50:
            return "2:2"
        elif percentage >= 40:
            return "3rd"
        else:
            return "Fail"


def is_m_level_degree(degree_level):
    return bool(degree_level and isinstance(degree_level, str) and degree_level.strip().lower().startswith('m'))


def rubric_marks_match_degree(rubric_marks, degree_level):
    labels = [str(b.get("grade", "")) for b in rubric_marks or []]
    has_m_level_labels = any(any(s in label for s in ("Dist", "Merit", "Pass")) for label in labels)
    has_third_labels = any("3rd" in label for label in labels)
    if is_m_level_degree(degree_level):
        return has_m_level_labels and not has_third_labels
    return not has_m_level_labels


def parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def assessment_confirm_context(headers, mappings, uploaded_data, error=None):
    import json as _json

    all_rubric_marks = {}
    for cat in mappings.get("categories", []):
        if cat.get("type") == "information":
            continue
        max_marks = cat.get("max_marks", 100)
        col = cat["column"]
        all_rubric_marks[col] = {
            sub: calculate_grade_bands(max_marks, sub, degree_level=mappings.get("degree_level", "BEng"))
            for sub in ("none", "high_low", "high_mid_low")
        }

    return {
        "headers": headers,
        "mappings": mappings,
        "sample_rows": uploaded_data[:3],
        "all_rubric_marks_json": _json.dumps(all_rubric_marks),
        "error": error,
    }



# ---------------------------------------------------------------------------
# Grade-string sets used for rubric column detection
# ---------------------------------------------------------------------------
_GRADE_STRINGS_NONE = {
    # Qualified 1st variants (used when no external subdivision is applied)
    "max 1st", "high 1st", "mid 1st", "low 1st",
    # Bare grade names — used in simple rubric columns with no subdivision
    "1st", "2:1", "2:2", "3rd", "fail",
}
_GRADE_STRINGS_HIGH_LOW = {
    "max 1st", "high 1st", "low 1st",
    "high 2:1", "low 2:1",
    "high 2:2", "low 2:2",
    "high 3rd", "low 3rd",
}
_GRADE_STRINGS_HIGH_MID_LOW = {
    "max 1st", "high 1st", "mid 1st", "low 1st",
    "high 2:1", "mid 2:1", "low 2:1",
    "high 2:2", "mid 2:2", "low 2:2",
    "high 3rd", "mid 3rd", "low 3rd",
}
_FAIL_STRINGS = {"close fail", "fail", "poor fail", "zero fail"}
_ALL_GRADE_STRINGS = (
    _GRADE_STRINGS_NONE
    | _GRADE_STRINGS_HIGH_LOW
    | _GRADE_STRINGS_HIGH_MID_LOW
    | _FAIL_STRINGS
    # M-level suffixed variants
    | {s.replace("1st", "1st/dist").replace("2:1", "2:1/merit").replace("2:2", "2:2/pass")
       for s in _GRADE_STRINGS_HIGH_MID_LOW}
)


def clean_category_title(title):
    """
    Remove denominator notations from the category title.
    E.g. "Design /30" -> "Design"
         "Implementation (40)" -> "Implementation"
         "Testing 30" -> "Testing"
         "Design (30%)" -> "Design"
    """
    cleaned = title
    # Remove "/30" or similar
    cleaned = re.sub(r'/\d+', '', cleaned)
    # Remove "(40%)" or "(40)" or similar
    cleaned = re.sub(r'\(\d+%\)', '', cleaned)
    cleaned = re.sub(r'\(\d+\)', '', cleaned)
    # Remove trailing digits at word boundaries
    cleaned = re.sub(r'\b\d+\b\s*$', '', cleaned)
    # Strip whitespace and trailing punctuation/special characters
    return cleaned.strip()


def is_information_column(header):
    """
    Check if a column header suggests it contains information/experimental data
    rather than a numeric or grade-based mark.
    """
    hl = header.lower()
    # If it contains grading-related terms, it is a mark, not information
    if any(term in hl for term in ("mark", "grade", "score", "total", "final")):
        return False
    # Check info keywords
    info_keywords = (
        "load", "time", "duration", "performance", "speed", "distance",
        "mass", "force", "height", "temp", "sec", "ms", "kg", "velocity",
        "acceleration"
    )
    return any(kw in hl for kw in info_keywords)


def infer_unit(header):
    """
    Infer the unit label from the column header.
    E.g. "Max Load (N)" -> "N"
         "Time / s" -> "s"
         "Mass [kg]" -> "kg"
    """
    hl = header.lower()
    # Try / unit
    match = re.search(r'/\s*([a-zA-Z]+)\b', header)
    if not match:
        # Try (unit)
        match = re.search(r'\(\s*([a-zA-Z]+)\s*\)', header)
    if not match:
        # Try [unit]
        match = re.search(r'\[\s*([a-zA-Z]+)\s*\]', header)

    if match:
        unit = match.group(1).strip()
        # Ensure it's not a number/denominator and is reasonably short
        if not unit.isdigit() and len(unit) <= 7:
            return unit

    # Basic substring fallbacks
    for unit_word in ("seconds", "ms", "kg", "meters", "sec"):
        if f" {unit_word}" in hl or f"({unit_word}" in hl:
            return unit_word

    return ""


def infer_rubric_type(column_values):
    """
    Given a list of raw cell values from one column, return:
        ("grade", subdivision)  if ≥70% are known UK grade strings
        ("numeric", "none")     otherwise

    subdivision is one of "none", "high_low", "high_mid_low".
    """
    non_null = [v for v in column_values if v is not None]
    if not non_null:
        return "numeric", "none"

    normalised = [str(v).strip().lower() for v in non_null]
    matched = sum(1 for v in normalised if v in _ALL_GRADE_STRINGS)
    if matched / len(non_null) < 0.7:
        return "numeric", "none"

    # Detect which subdivision is in use
    # "Mid X:Y" patterns (excluding Mid 1st which appears in 'none') distinguish high_mid_low
    if any("mid 2:" in v or "mid 3rd" in v for v in normalised):
        return "grade", "high_mid_low"
    # "High/Low X:Y" patterns (on non-1st bands) distinguish high_low
    if any(
        any(p in v for p in ("high 2:", "low 2:", "high 3rd", "low 3rd"))
        for v in normalised
    ):
        return "grade", "high_low"
    return "grade", "none"


def rubric_mark_from_label(grade_label, rubric_marks):
    """
    Look up a grade string (e.g. "Mid 2:1") in the rubric_marks list and
    return the corresponding numeric mark.  Returns 0 if not found.
    """
    label_lower = str(grade_label).strip().lower()
    for band in rubric_marks:
        if band["grade"].lower() == label_lower:
            return band["marks"]
    return 0


def build_feedback_sheet_layout_rows(layout):
    """
    Convert the flat layout list into a list of "rows" suitable for
    Feedback Sheet table-cell rendering.

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


def numeric_mark(value):
    try:
        return float(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def category_mark_value(student_row, category, degree_level):
    raw_mark = student_row.get(category["column"], 0)
    grade_awarded = None

    if category["type"] == "grade":
        rubric_marks = category.get("rubric_marks") or calculate_grade_bands(
            category["max_marks"],
            category.get("subdivision", "none"),
            degree_level=degree_level,
        )
        mark_val = rubric_mark_from_label(raw_mark, rubric_marks)
        grade_awarded = str(raw_mark).strip() if raw_mark else None
    else:
        mark_val = numeric_mark(raw_mark)

    return mark_val, grade_awarded


def build_assessment_cohort_stats(uploaded_data, categories, degree_level):
    cohort_final_marks = []
    category_cohort_marks = {cat["column"]: [] for cat in categories}

    for row in uploaded_data:
        student_total = 0
        for cat in categories:
            mark_val, _ = category_mark_value(row, cat, degree_level)
            category_cohort_marks[cat["column"]].append(mark_val)
            if cat.get("type") != "information":
                student_total += mark_val
        cohort_final_marks.append(student_total)

    category_averages = {}
    for cat in categories:
        vals = category_cohort_marks[cat["column"]]
        category_averages[cat["column"]] = sum(vals) / len(vals) if vals else 0

    return cohort_final_marks, category_averages


def build_assessment_student_context(student_row, student_index, mappings, category_averages, cohort_final_marks):
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    degree_level = mappings["degree_level"]
    subdivision = mappings["subdivision"]
    categories = mappings["categories"]
    total_max_marks = sum(cat["max_marks"] for cat in categories if cat.get("type") != "information")

    student_name = str(student_row.get(col_name, f"Student {student_index+1}")).strip()
    student_id = str(student_row.get(col_id, f"ID-{student_index+1}")).strip()
    student_total_score = 0
    student_categories_data = []
    radar_labels = []
    student_radar_percentages = []
    avg_radar_percentages = []

    for cat in categories:
        col = cat["column"]
        max_marks = cat.get("max_marks")
        mark_val, grade_awarded = category_mark_value(student_row, cat, degree_level)

        if cat.get("type") != "information":
            student_total_score += mark_val
            student_pct = (mark_val / max_marks) * 100 if max_marks and max_marks > 0 else 0
            avg_pct = (category_averages[col] / max_marks) * 100 if max_marks and max_marks > 0 else 0

            radar_labels.append(clean_category_title(col))
            student_radar_percentages.append(student_pct)
            avg_radar_percentages.append(avg_pct)

            calculated_grade_band = grade_for_percentage_and_degree(student_pct, degree_level)
        else:
            student_pct = 0
            calculated_grade_band = None

        student_categories_data.append({
            "label": clean_category_title(col),
            "mark": mark_val,
            "max_marks": max_marks,
            "grade_awarded": grade_awarded,
            "feedback_comment": student_row.get(cat.get("comments_column", ""), ""),
            "is_grade": cat["type"] == "grade",
            "is_information": cat["type"] == "information",
            "unit": cat.get("unit", ""),
            "calculated_grade_band": calculated_grade_band,
        })

    overall_pct = (student_total_score / total_max_marks) * 100 if total_max_marks > 0 else 0
    radar_svg = generate_radar_chart(radar_labels, student_radar_percentages, avg_radar_percentages)
    hist_svg = generate_cohort_histogram(
        cohort_final_marks,
        student_total_score,
        max_score=total_max_marks,
        subdivision=subdivision,
    )

    return {
        "student_name": student_name,
        "student_id": student_id,
        "categories": student_categories_data,
        "total_score": student_total_score,
        "total_max_marks": total_max_marks,
        "overall_grade": grade_for_percentage_and_degree(overall_pct, degree_level),
        "overall_percentage": round(overall_pct),
        "radar_base64": base64.b64encode(radar_svg.encode("utf-8")).decode("utf-8") if radar_svg else "",
        "hist_base64": base64.b64encode(hist_svg.encode("utf-8")).decode("utf-8") if hist_svg else "",
        "degree_level": degree_level,
        "module_code": mappings.get("module_code", "COMP101"),
        "module_title": mappings.get("module_title", "Module Performance"),
        "assessment_title": mappings.get("assessment_title", "Feedback Report"),
        "academic_year": mappings.get("academic_year", "2025/2026"),
    }


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
                
                # Check if values in this column are predominantly numeric OR grade strings
                col_values = [r.get(h) for r in data_rows]
                non_null = [v for v in col_values if v is not None]
                total_valid = len(non_null)

                if total_valid == 0:
                    continue

                numeric_count = 0
                for v in non_null:
                    try:
                        float(v)
                        numeric_count += 1
                    except (ValueError, TypeError):
                        pass

                is_numeric_candidate = (numeric_count / total_valid) >= 0.7
                is_rubric_candidate = not is_numeric_candidate and infer_rubric_type(col_values)[0] == "grade"

                if is_numeric_candidate or is_rubric_candidate:
                    candidate_categories.append(h)

            
            # Build category configurations with max marks, comments, and rubric detection
            for cat in candidate_categories:
                if is_information_column(cat):
                    cat_type = "information"
                    max_marks = None
                    cat_subdivision = "none"
                    rubric_marks = []
                    unit = infer_unit(cat)
                else:
                    unit = ""
                    # Infer max marks (denominator) from header (e.g. Design /30, Design (30), Design 30)
                    max_marks = 100  # default fallback
                    denom_match = re.search(r'/(\d+)', cat)
                    if not denom_match:
                        denom_match = re.search(r'\((\d+)\)', cat)
                    if not denom_match:
                        denom_match = re.search(r'\b(\d+)$', cat)

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
                
                    # Detect rubric (grade string) columns
                    col_values = [r.get(cat) for r in data_rows]
                    cat_type, cat_subdivision = infer_rubric_type(col_values)
                
                # Weighting is no longer used
                weight = None

                # Find matching feedback comments column
                comments_col = ""
                cat_clean = re.sub(r'[/()%\d\s]+', '', cat).lower()  # e.g. "design"
                for h in headers:
                    hl = h.lower()
                    if h != cat and ("comment" in hl or "feedback" in hl) and cat_clean in hl:
                        comments_col = h
                        break

                # Pre-compute rubric band marks so confirm page can display them
                rubric_marks = []
                if cat_type == "grade":
                    rubric_marks = calculate_grade_bands(
                        max_marks,
                        cat_subdivision,
                        degree_level=inferred_mappings["degree_level"],
                    )

                inferred_mappings["categories"].append({
                    "column": cat,
                    "max_marks": max_marks,
                    "weight": weight,
                    "comments_column": comments_col,
                    "type": cat_type,
                    "subdivision": cat_subdivision,
                    "rubric_marks": rubric_marks,
                    "unit": unit,
                })

            # Set global subdivision to the most common one detected across rubric columns
            rubric_subdivisions = [
                c["subdivision"] for c in inferred_mappings["categories"]
                if c["type"] == "grade" and c["subdivision"] != "none"
            ]
            if rubric_subdivisions:
                from collections import Counter
                inferred_mappings["subdivision"] = Counter(rubric_subdivisions).most_common(1)[0][0]

            has_mark_or_rubric = any(c["type"] in ("numeric", "grade") for c in inferred_mappings["categories"])
            if not inferred_mappings["categories"] or not has_mark_or_rubric:
                return render(request, "assessment_feedback/upload.html", {
                    "error": "No grading categories were detected. Please upload a sheet with numeric mark columns or rubric grade columns."
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


def rubric_bands_api(request):
    """
    Lightweight JSON API — returns grade band marks for a given max_marks +
    subdivision combination.  Called by the confirm page JS when the user
    edits the Max Marks field on a rubric-type category row.

    GET /assessment-feedback/rubric-bands/?max_marks=30&subdivision=high_low
    """
    import json as _json
    try:
        max_marks  = int(request.GET.get("max_marks", 100))
        subdivision = request.GET.get("subdivision", "none")
        degree_level = request.GET.get("degree_level", "BEng")
        if subdivision not in ("none", "high_low", "high_mid_low"):
            subdivision = "none"
        bands = calculate_grade_bands(max_marks, subdivision, degree_level=degree_level)
        return HttpResponse(_json.dumps(bands), content_type="application/json")
    except (ValueError, TypeError):
        return HttpResponse(
            _json.dumps({"error": "Invalid parameters"}),
            content_type="application/json",
            status=400,
        )


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

    if not mappings.get("categories"):
        return render(request, "assessment_feedback/confirm.html",
                      assessment_confirm_context(headers, mappings, uploaded_data, "No grading categories were detected."))
        
    if request.method == "POST":
        # Read student identifiers mapping
        mappings["col_student_name"] = request.POST.get("col_student_name")
        mappings["col_student_id"] = request.POST.get("col_student_id")
        mappings["degree_level"] = request.POST.get("degree_level", "BEng")
        
        # Read updated categories configs
        updated_categories = []
        has_mark_or_rubric = False
        for idx, cat_dict in enumerate(mappings["categories"]):
            col_name = cat_dict["column"]
            cat_type = request.POST.get(f"type_{idx}", "numeric")
            comments_col = request.POST.get(f"comments_{idx}")
            
            if cat_type in ("numeric", "grade"):
                has_mark_or_rubric = True
                max_marks = parse_positive_int(request.POST.get(f"max_{idx}"))
                if max_marks is None:
                    return render(request, "assessment_feedback/confirm.html",
                                  assessment_confirm_context(
                                      headers,
                                      mappings,
                                      uploaded_data,
                                      f"Max marks for {col_name} must be a positive whole number.",
                                  ))
                unit_val = ""
            else:
                max_marks = None
                unit_val = request.POST.get(f"unit_{idx}", "").strip()

            cat_subdivision = cat_dict.get("subdivision", "none")

            # Rebuild rubric_marks from submitted band mark inputs (user may have edited them)
            existing_rubric = cat_dict.get("rubric_marks", [])
            rubric_marks = []
            if cat_type == "grade":
                if existing_rubric and rubric_marks_match_degree(existing_rubric, mappings["degree_level"]):
                    for band_idx, band in enumerate(existing_rubric):
                        submitted_mark = request.POST.get(f"rubric_mark_{idx}_{band_idx}")
                        try:
                            mark_val = int(submitted_mark)
                        except (TypeError, ValueError):
                            mark_val = band["marks"]
                        rubric_marks.append({"grade": band["grade"], "marks": mark_val})
                else:
                    rubric_marks = calculate_grade_bands(
                        max_marks,
                        cat_subdivision,
                        degree_level=mappings["degree_level"],
                    )

            updated_categories.append({
                "column": col_name,
                "max_marks": max_marks,
                "weight": None,
                "comments_column": comments_col,
                "type": cat_type,
                "subdivision": cat_subdivision,
                "rubric_marks": rubric_marks,
                "unit": unit_val,
            })
            
        if not has_mark_or_rubric:
            return render(request, "assessment_feedback/confirm.html",
                          assessment_confirm_context(
                              headers,
                              mappings,
                              uploaded_data,
                              "You must have at least one numeric Mark or Rubric grade category.",
                          ))

        mappings["categories"] = updated_categories

        # Recalculate global subdivision based on the most common subdivision of active grade columns
        rubric_subdivisions = [
            c["subdivision"] for c in updated_categories
            if c["type"] == "grade" and c["subdivision"] != "none"
        ]
        if rubric_subdivisions:
            from collections import Counter
            mappings["subdivision"] = Counter(rubric_subdivisions).most_common(1)[0][0]
        else:
            mappings["subdivision"] = "none"

        request.session["mappings"] = mappings
        request.session.modified = True
        
        return redirect("configure_layout")
        
    return render(request, "assessment_feedback/confirm.html",
                  assessment_confirm_context(headers, mappings, uploaded_data))


def ensure_layout_defaults(layout, session=None):
    """
    Ensure all default blocks exist in the loaded layout to handle stale sessions.
    """
    default_blocks = {
        "category_marks": {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True},
        "feedback": {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True},
        "general_feedback": {"id": "general_feedback", "name": "General Feedback", "width": "full", "enabled": False},
        "radar_chart": {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True},
        "histogram": {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": True},
    }
    if not layout:
        return list(default_blocks.values())

    modified = False
    # Check for missing blocks
    for bid, block_def in default_blocks.items():
        if not any(b["id"] == bid for b in layout):
            # Insert at default position or append
            if bid == "general_feedback":
                # Insert after feedback if present
                inserted = False
                for idx, b in enumerate(layout):
                    if b["id"] == "feedback":
                        layout.insert(idx + 1, block_def.copy())
                        inserted = True
                        break
                if not inserted:
                    layout.append(block_def.copy())
            else:
                layout.append(block_def.copy())
            modified = True

    if modified and session is not None:
        session["layout"] = layout
        session.modified = True

    return layout


def configure_layout(request):
    """
    Step 2.5: Feedback Sheet Layout Builder Configuration Page
    Allows academics to control their positioning (ordering), set grid widths,
    and preview any student's compiled Feedback Sheet in real-time.
    """
    headers = request.session.get("headers")
    mappings = request.session.get("mappings")
    uploaded_data = request.session.get("uploaded_data")
    
    if not headers or not mappings or not uploaded_data:
        return redirect("upload_file")
        
    layout = request.session.get("layout")
    layout = ensure_layout_defaults(layout, session=request.session)
    
    if request.method == "POST":
        block_order = request.POST.get("block_order", "").split(",")
        if not any(block_order):
            block_order = ["category_marks", "feedback", "general_feedback", "radar_chart", "histogram"]
            
        updated_layout = []
        name_map = {
            "category_marks": "Category Marks",
            "feedback": "Feedback Comments",
            "general_feedback": "General Feedback",
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
                
        show_numeric_grade_bands = request.POST.get("show_numeric_grade_bands") == "true"
        request.session["show_numeric_grade_bands"] = show_numeric_grade_bands

        general_comments = request.POST.get("general_comments", "").strip()
        request.session["general_comments"] = general_comments

        if updated_layout:
            request.session["layout"] = updated_layout
            request.session.modified = True
            
        return redirect("process_feedback")

    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    categories = mappings["categories"]

    cohort_final_marks, category_averages = build_assessment_cohort_stats(
        uploaded_data,
        categories,
        mappings["degree_level"],
    )

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
        preview_student = build_assessment_student_context(
            student_row,
            preview_student_index,
            mappings,
            category_averages,
            cohort_final_marks,
        )

    show_numeric_grade_bands = request.session.get("show_numeric_grade_bands", False)
    general_comments = request.session.get("general_comments", "")

    return render(request, "assessment_feedback/configure_layout.html", {
        "layout": layout,
        "preview_student_index": preview_student_index,
        "students_list": students_list,
        "preview_student": preview_student,
        "show_numeric_grade_bands": show_numeric_grade_bands,
        "general_comments": general_comments,
    })


def process_feedback(request):
    """
    Step 3: Processing & HTML ZIP Stream
    Computes cohort stats (averages, final score arrays), loops over student rows to
    generate custom Matplotlib radar/hist charts, compiles self-contained HTML sheets,
    and returns a downloadable ZIP archive with zero data persistence.
    """
    uploaded_data = request.session.get("uploaded_data")
    mappings = request.session.get("mappings")
    show_numeric_grade_bands = request.session.get("show_numeric_grade_bands", False)
    
    if not uploaded_data or not mappings:
        return redirect("upload_file")
        
    layout = request.session.get("layout")
    layout = ensure_layout_defaults(layout, session=request.session)
        
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    categories = mappings["categories"]

    cohort_final_marks, category_averages = build_assessment_cohort_stats(
        uploaded_data,
        categories,
        mappings["degree_level"],
    )
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, student_row in enumerate(uploaded_data):
            student_name = str(student_row.get(col_name, f"Student {idx+1}")).strip()
            student_id = str(student_row.get(col_id, f"ID-{idx+1}")).strip()
            
            if not student_name and not student_id:
                continue

            student_context = build_assessment_student_context(
                student_row,
                idx,
                mappings,
                category_averages,
                cohort_final_marks,
            )
            context = {
                **student_context,
                "layout": layout,
                "layout_rows": build_feedback_sheet_layout_rows(layout),
                "show_numeric_grade_bands": show_numeric_grade_bands,
                "general_comments": request.session.get("general_comments", ""),
            }
            
            html_content = render_feedback_sheet_template(request, context)
            
            filename = f"{slugify(student_id)}_{slugify(student_name)}.html"
            zip_file.writestr(filename, html_content.encode('utf-8'))
            
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=student_feedback_reports.zip"
    return response


def render_feedback_sheet_template(request, context):
    """
    Renders the beautiful glassmorphic feedback sheet directly
    to a compiled raw HTML string in context.
    """
    return render_to_string("assessment_feedback/feedback_sheet.html", context, request=request)
