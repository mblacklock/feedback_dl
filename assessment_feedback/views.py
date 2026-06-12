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
from core.utils.student_id import format_student_id


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


def get_student_name(student_row, student_index, mappings):
    if mappings.get("name_mode") == "split":
        first = str(student_row.get(mappings.get("col_first_name", ""), "")).strip()
        last = str(student_row.get(mappings.get("col_last_name", ""), "")).strip()
        return f"{first} {last}".strip() or f"Student {student_index+1}"
    return str(student_row.get(mappings.get("col_student_name", ""), f"Student {student_index+1}")).strip()


def parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _try_float(value):
    """Return float(value) if convertible, else None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def column_letter(idx):
    """Convert a 0-based column index to a spreadsheet-style letter label (A, B, …, Z, AA, …)."""
    result = ""
    n = idx + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def assessment_confirm_context(headers, mappings, uploaded_data, error=None):
    import json as _json

    all_rubric_marks = {}
    for cat in mappings.get("categories", []):
        # Skip non-data rows — they have no rubric marks
        if cat.get("type") in ("information", "feedback_only"):
            continue
        if cat.get("row_type", "criterion") == "divider":
            continue
        max_marks = cat.get("max_marks") or 100
        col = cat["column"]
        all_rubric_marks[col] = {
            sub: calculate_grade_bands(max_marks, sub, degree_level=mappings.get("degree_level", "BEng"))
            for sub in ("none", "high_low", "high_mid_low")
        }

    # Build (raw_value, display_label) pairs so templates can show <A> for blank headers
    headers_with_labels = [
        (h, h if h else f"<{column_letter(i)}>")
        for i, h in enumerate(headers)
    ]

    # Headers not already claimed by a special role or existing category row.
    # Used by the "+ Add Column" dropdown on the confirm page.
    _assigned_special = {
        mappings.get("col_student_name", ""),
        mappings.get("col_student_id", ""),
        mappings.get("col_overall_mark", ""),
        mappings.get("col_first_name", ""),
        mappings.get("col_last_name", ""),
        mappings.get("col_group", ""),
    }
    _assigned_special.discard("")
    _category_cols = {cat["column"] for cat in mappings.get("categories", [])}
    _used_cols = _assigned_special | _category_cols
    _label_map = {raw: label for raw, label in headers_with_labels}

    def is_col_numeric(col):
        for row in uploaded_data:
            val = row.get(col)
            if val is not None and val != "":
                try:
                    float(str(val).strip().replace("%", ""))
                except ValueError:
                    return False
        return True

    available_headers = [
        {"raw": h, "label": _label_map.get(h, h), "is_numeric": is_col_numeric(h)}
        for h in headers
        if h not in _used_cols
    ]

    return {
        "headers": headers,
        "headers_with_labels": headers_with_labels,
        "header_label_map": {raw: label for raw, label in headers_with_labels},
        "mappings": mappings,
        "sample_rows": uploaded_data[:3],
        "all_rubric_marks_json": _json.dumps(all_rubric_marks),
        "available_headers_json": _json.dumps(available_headers),
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
    cleaned_str = cleaned.strip()
    if not cleaned_str:
        # Nothing survived cleaning — the title was entirely numeric (e.g. "002").
        # Return the original so purely-numeric component labels are preserved.
        return title.strip()
    if cleaned_str.isupper():
        return cleaned_str.capitalize()
    return cleaned_str


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
            # Look ahead for a second consecutive half block that does not force its own row,
            # and only if the current block does not force its own row.
            if (not block.get("own_row") and
                i + 1 < len(enabled) and
                enabled[i + 1]["width"] == "half" and
                not enabled[i + 1].get("own_row")):
                rows.append({"type": "half-pair", "blocks": [block, enabled[i + 1]]})
                i += 2
            else:
                rows.append({"type": "half-single", "blocks": [block]})
                i += 1
    return rows


def numeric_mark(value):
    try:
        return round(float(value), 10) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def category_mark_value(student_row, category, degree_level):
    raw_mark = student_row.get(category["column"], 0)
    grade_awarded = None

    if category["type"] == "grade":
        rubric_marks = category.get("rubric_marks") or calculate_grade_bands(
            category.get("max_marks") or 100,
            category.get("subdivision", "none"),
            degree_level=degree_level,
        )
        mark_val = rubric_mark_from_label(raw_mark, rubric_marks)
        grade_awarded = str(raw_mark).strip() if raw_mark else None
    else:
        mark_val = numeric_mark(raw_mark)

    return mark_val, grade_awarded


def build_assessment_cohort_stats(uploaded_data, categories, degree_level, col_overall_mark=None, col_group=None):
    active_categories = [cat for cat in categories if cat["column"] != col_overall_mark] if col_overall_mark else list(categories)
    if col_group:
        active_categories = [cat for cat in active_categories if cat["column"] != col_group]
    # Filter out feedback_only columns from statistics/marks calculations
    active_categories = [cat for cat in active_categories if cat.get("type") != "feedback_only"]
    cohort_final_marks = []
    category_cohort_marks = {cat["column"]: [] for cat in active_categories}

    for row in uploaded_data:
        for cat in active_categories:
            mark_val, _ = category_mark_value(row, cat, degree_level)
            category_cohort_marks[cat["column"]].append(mark_val)
            
        if col_overall_mark:
            student_total = numeric_mark(row.get(col_overall_mark, 0))
        else:
            student_total = 0
            for cat in active_categories:
                if cat.get("type") != "information":
                    mark_val, _ = category_mark_value(row, cat, degree_level)
                    student_total += mark_val
        cohort_final_marks.append(student_total)

    category_averages = {}
    for cat in active_categories:
        vals = category_cohort_marks[cat["column"]]
        category_averages[cat["column"]] = sum(vals) / len(vals) if vals else 0

    return cohort_final_marks, category_averages


def build_assessment_student_context(student_row, student_index, mappings, category_averages, cohort_final_marks):
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    degree_level = mappings["degree_level"]
    subdivision = mappings["subdivision"]
    categories = mappings["categories"]
    col_overall_mark = mappings.get("col_overall_mark")
    
    col_group = mappings.get("col_group", "")

    active_categories = [cat for cat in categories if cat["column"] != col_overall_mark] if col_overall_mark else list(categories)
    if col_group:
        active_categories = [cat for cat in active_categories if cat["column"] != col_group]
    if col_overall_mark:
        total_max_marks = 100  # default fallback
        for cat in categories:
            if cat["column"] == col_overall_mark:
                total_max_marks = cat.get("max_marks") or 100
                break
    else:
        total_max_marks = sum(
            cat["max_marks"] for cat in active_categories 
            if cat.get("type") not in ("information", "feedback_only") and cat.get("max_marks") is not None
        )

    student_name = get_student_name(student_row, student_index, mappings)
    raw_student_id = student_row.get(col_id)
    student_id = format_student_id(raw_student_id) if raw_student_id is not None else f"ID-{student_index+1}"
    
    if col_overall_mark:
        student_total_score = numeric_mark(student_row.get(col_overall_mark, 0))
    else:
        student_total_score = 0
        
    student_categories_data = []
    radar_labels = []
    student_radar_percentages = []
    avg_radar_percentages = []

    for cat in active_categories:
        col = cat["column"]
        row_type = cat.get("row_type", "criterion")
        cat_label = cat.get("label") or clean_category_title(col)

        # Divider rows are purely presentational — mark the previous category with a divider.
        if row_type == "divider":
            if student_categories_data:
                student_categories_data[-1]["divider_below"] = True
            continue

        max_marks = cat.get("max_marks")
        is_feedback_only = cat.get("type") == "feedback_only"

        if is_feedback_only:
            mark_val = None
            grade_awarded = None
            calculated_grade_band = None
            feedback_comment = str(student_row.get(col) or "").strip()
        else:
            mark_val, grade_awarded = category_mark_value(student_row, cat, degree_level)
            feedback_comment = student_row.get(cat.get("comments_column", ""), "")

        if cat.get("type") != "information" and not is_feedback_only:
            if not col_overall_mark:
                student_total_score += mark_val
            student_pct = (mark_val / max_marks) * 100 if max_marks and max_marks > 0 else 0
            avg_pct = (category_averages[col] / max_marks) * 100 if max_marks and max_marks > 0 else 0

            if not cat.get("exclude_radar", False):
                radar_labels.append(cat_label)
                student_radar_percentages.append(student_pct)
                avg_radar_percentages.append(avg_pct)

            calculated_grade_band = grade_for_percentage_and_degree(student_pct, degree_level)
        else:
            student_pct = 0
            calculated_grade_band = None

        student_categories_data.append({
            "column": col,
            "label": cat_label,
            "row_type": row_type,
            "mark": mark_val,
            "max_marks": max_marks,
            "grade_awarded": grade_awarded,
            "feedback_comment": feedback_comment,
            "is_grade": cat["type"] == "grade",
            "is_information": cat["type"] == "information",
            "is_feedback_only": is_feedback_only,
            "unit": cat.get("unit", ""),
            "calculated_grade_band": calculated_grade_band,
            "divider_below": cat.get("divider_below", False),
            "header_below": False,
        })

    for i in range(len(student_categories_data) - 1):
        if student_categories_data[i + 1].get("row_type") == "header":
            student_categories_data[i]["header_below"] = True

    overall_pct = (student_total_score / total_max_marks) * 100 if total_max_marks > 0 else 0
    radar_svg = generate_radar_chart(radar_labels, student_radar_percentages, avg_radar_percentages)
    
    cohort_final_percentages = [
        (mark / total_max_marks) * 100 for mark in cohort_final_marks
    ] if total_max_marks > 0 else []
    
    hist_svg = generate_cohort_histogram(
        cohort_final_percentages,
        overall_pct,
        degree_level=mappings.get("degree_level"),
    )

    return {
        "student_name": student_name,
        "student_id": student_id,
        "student_group": str(student_row.get(mappings.get("col_group", ""), "") or "").strip(),
        "categories": student_categories_data,
        "total_score": student_total_score,
        "total_max_marks": total_max_marks,
        "overall_grade": grade_for_percentage_and_degree(overall_pct, degree_level),
        "overall_percentage": round(overall_pct),
        "radar_base64": base64.b64encode(radar_svg.encode("utf-8")).decode("utf-8") if radar_svg else "",
        "hist_base64": base64.b64encode(hist_svg.encode("utf-8")).decode("utf-8") if hist_svg else "",
        "radar_svg": radar_svg,
        "hist_svg": hist_svg,
        "degree_level": degree_level,
        "module_code": mappings.get("module_code", "COMP101"),
        "module_title": mappings.get("module_title", "Module Performance"),
        "assessment_component": mappings.get("assessment_component", ""),
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

            # Deduplicate headers: first-occurrence wins for each non-blank header name.
            # Spreadsheets often have a summary table to the right of the data that
            # repeats the same column labels — this causes row_dict overwrites and
            # confuses category detection.
            header_col_index = {}  # header name -> first column index that uses it
            for idx, h in enumerate(headers):
                if h and h not in header_col_index:
                    header_col_index[h] = idx
            unique_headers = list(header_col_index.keys())

            # Extract student rows (ignoring fully empty rows).
            # Use header_col_index so first-occurrence column value is always used.
            data_rows = []
            for r in rows[1:]:
                if any(cell is not None for cell in r):
                    row_dict = {
                        h: (r[idx] if idx < len(r) else None)
                        for h, idx in header_col_index.items()
                    }
                    data_rows.append(row_dict)
            
            # Check for split first/last name columns
            first_name_col = ""
            last_name_col = ""
            group_col = ""
            group_keywords = ("group", "team", "cohort", "class", "section", "lab", "tutorial")
            for h in unique_headers:
                hl = h.lower()
                if "first" in hl or "forename" in hl or "given" in hl:
                    first_name_col = h
                elif "last" in hl or "surname" in hl or "family" in hl:
                    last_name_col = h
                elif any(kw in hl for kw in group_keywords) and not group_col:
                    group_col = h

            # Auto-infer column roles
            inferred_mappings = {
                "col_student_name": "",
                "col_student_id": "",
                "col_overall_mark": "",
                "col_group": "",
                "col_first_name": first_name_col,
                "col_last_name": last_name_col,
                "name_mode": "split" if (first_name_col and last_name_col) else "full",
                "categories": [],
                "degree_level": "BEng",  # default
                "subdivision": "none",   # default
                "module_code": "COMP101",
                "module_title": "Module Performance",
                "assessment_component": "",
                "assessment_title": "Feedback Report",
                "academic_year": "2025/2026",
            }

            # Validate group_col: confirm values are non-numeric (i.e. real group labels)
            if group_col:
                inferred_mappings["col_group"] = group_col
            
            # 1. Infer Name, ID & Overall Mark
            # ID is checked first so "Student ID" is never mistaken for a name column.
            for h in unique_headers:
                hl = h.lower()
                is_id_like = "id" in hl or "number" in hl or "code" in hl

                if is_id_like and not inferred_mappings["col_student_id"]:
                    inferred_mappings["col_student_id"] = h
                elif (("name" in hl or "student" in hl) and not is_id_like
                        and not inferred_mappings["col_student_name"]):
                    if h != first_name_col and h != last_name_col:
                        inferred_mappings["col_student_name"] = h
                elif (("total" in hl or "final" in hl or "overall" in hl)
                        and not inferred_mappings.get("col_overall_mark")):
                    if not is_id_like:
                        inferred_mappings["col_overall_mark"] = h
            
            # Fallback if names/ids not matched
            if inferred_mappings["name_mode"] == "split":
                if not inferred_mappings["col_student_name"]:
                    inferred_mappings["col_student_name"] = first_name_col
            else:
                if not inferred_mappings["col_student_name"] and unique_headers:
                    inferred_mappings["col_student_name"] = unique_headers[0]
            if not inferred_mappings["col_student_id"] and len(unique_headers) > 1:
                inferred_mappings["col_student_id"] = unique_headers[1]
                
            # Columns known to be non-category (text/comment columns)
            comment_keywords = ("comment", "feedback", "notes", "remarks", "text")

            # 2. Infer Categories & Comments
            # We look for numeric columns as category candidates.
            # unique_headers is already deduplicated, so no need for seen_headers.
            candidate_categories = []
            for h in unique_headers:
                if (h == inferred_mappings["col_student_name"] or
                    h == inferred_mappings["col_student_id"] or
                    h == inferred_mappings.get("col_first_name") or
                    h == inferred_mappings.get("col_last_name")):
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

                # Find matching feedback comments column.
                # Only attempt a match when the cleaned category name is long enough
                # to be meaningful — short/blank names would match any comment column.
                comments_col = ""
                cat_clean = re.sub(r'[/()%\d\s]+', '', cat).lower()  # e.g. "design"
                if len(cat_clean) >= 3:
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
                    "label": clean_category_title(cat),
                    "row_type": "criterion",
                    "max_marks": max_marks,
                    "weight": weight,
                    "comments_column": comments_col,
                    "type": cat_type,
                    "subdivision": cat_subdivision,
                    "rubric_marks": rubric_marks,
                    "unit": unit,
                    "exclude_radar": cat_type in ("information", "feedback_only"),
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
            request.session["headers"] = unique_headers
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
        mappings["col_student_name"] = request.POST.get("col_student_name", "")
        mappings["col_student_id"] = request.POST.get("col_student_id", "")
        mappings["col_overall_mark"] = request.POST.get("col_overall_mark", "")
        mappings["col_group"] = request.POST.get("col_group", "")
        mappings["name_mode"] = request.POST.get("name_mode", "full")
        mappings["col_first_name"] = request.POST.get("col_first_name", "")
        mappings["col_last_name"] = request.POST.get("col_last_name", "")
        mappings["degree_level"] = request.POST.get("degree_level", "BEng")
        
        # Read module and assessment details
        mappings["module_code"] = request.POST.get("module_code", "").strip() or "COMP101"
        mappings["module_title"] = request.POST.get("module_title", "").strip() or "Module Performance"
        mappings["assessment_component"] = request.POST.get("assessment_component", "").strip()
        mappings["assessment_title"] = request.POST.get("assessment_title", "").strip() or "Feedback Report"
        mappings["academic_year"] = request.POST.get("academic_year", "").strip() or "2025/2026"
        
        # Read updated categories configs
        updated_categories = []
        has_mark_or_rubric = False

        # Determine if we use the col_name_N or positional loop
        use_col_name_loop = any(f"col_name_{i}" in request.POST for i in range(100))

        if use_col_name_loop:
            existing_cats_by_col = {cat["column"]: cat for cat in mappings.get("categories", [])}

            # Determine processing order from category_order (captures insert-above DOM order).
            # Fall back to sequential scan if not provided (e.g. old test data).
            category_order_str = request.POST.get("category_order", "")
            if category_order_str:
                order_indices = [s.strip() for s in category_order_str.split(",") if s.strip()]
            else:
                seq = 0
                order_indices = []
                while f"col_name_{seq}" in request.POST:
                    order_indices.append(str(seq))
                    seq += 1

            for idx_str in order_indices:
                if request.POST.get(f"removed_{idx_str}") == "1":
                    continue

                col_name_key = f"col_name_{idx_str}"
                if col_name_key not in request.POST:
                    continue

                col_name = request.POST[col_name_key]
                row_type = request.POST.get(f"row_type_{idx_str}", "criterion")
                label_val = request.POST.get(f"label_{idx_str}", "").strip()

                # Divider rows are purely presentational — no marks needed.
                if row_type == "divider":
                    updated_categories.append({
                        "column": col_name,
                        "label": label_val,
                        "row_type": row_type,
                        "type": "feedback_only",
                        "max_marks": None,
                        "weight": None,
                        "comments_column": "",
                        "subdivision": "none",
                        "rubric_marks": [],
                        "unit": "",
                        "exclude_radar": True,
                    })
                    continue

                cat_dict = existing_cats_by_col.get(col_name, {})
                cat_type = request.POST.get(f"type_{idx_str}", "numeric")
                comments_col = request.POST.get(f"comments_{idx_str}")
                exclude_radar = (request.POST.get(f"include_radar_{idx_str}") != "on") if cat_type in ("numeric", "grade", "header") else True

                if cat_type in ("numeric", "grade"):
                    has_mark_or_rubric = True
                    max_marks = parse_positive_int(request.POST.get(f"max_{idx_str}"))
                    if max_marks is None:
                        return render(request, "assessment_feedback/confirm.html",
                                      assessment_confirm_context(
                                          headers,
                                          mappings,
                                          uploaded_data,
                                          f"Max marks for {col_name} must be a positive whole number.",
                                      ))
                    unit_val = ""
                elif cat_type == "information":
                    max_marks = None
                    unit_val = request.POST.get(f"unit_{idx_str}", "").strip()
                else:  # feedback_only
                    max_marks = None
                    unit_val = ""

                cat_subdivision = cat_dict.get("subdivision", "none")

                existing_rubric = cat_dict.get("rubric_marks", [])
                rubric_marks = []
                if cat_type == "grade":
                    if existing_rubric and rubric_marks_match_degree(existing_rubric, mappings["degree_level"]):
                        for band_idx, band in enumerate(existing_rubric):
                            submitted_mark = request.POST.get(f"rubric_mark_{idx_str}_{band_idx}")
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

                # Default label to clean title if user left it blank
                if not label_val:
                    label_val = clean_category_title(col_name)

                divider_below = (request.POST.get(f"divider_below_{idx_str}") == "1")

                updated_categories.append({
                    "column": col_name,
                    "label": label_val,
                    "row_type": row_type,
                    "max_marks": max_marks,
                    "weight": None,
                    "comments_column": comments_col,
                    "type": cat_type,
                    "subdivision": cat_subdivision,
                    "rubric_marks": rubric_marks,
                    "unit": unit_val,
                    "exclude_radar": exclude_radar,
                    "divider_below": divider_below,
                })
        else:
            # Fallback for old/test POST data (no col_name_N fields)
            for idx, cat_dict in enumerate(mappings["categories"]):
                col_name = cat_dict["column"]
                row_type = cat_dict.get("row_type", "criterion")
                label_val = ""  # will be resolved below
                cat_type = request.POST.get(f"type_{idx}", "numeric")
                comments_col = request.POST.get(f"comments_{idx}")
                exclude_radar = (request.POST.get(f"include_radar_{idx}") != "on") if cat_type in ("numeric", "grade") else True
                
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
                elif cat_type == "information":
                    max_marks = None
                    unit_val = request.POST.get(f"unit_{idx}", "").strip()
                else:  # feedback_only
                    max_marks = None
                    unit_val = ""
                    
                cat_subdivision = cat_dict.get("subdivision", "none")
                
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
                
                # Default label to clean title if user left it blank
                if not label_val:
                    label_val = cat_dict.get("label") or clean_category_title(col_name)

                divider_below = (request.POST.get(f"divider_below_{idx}") == "1") or cat_dict.get("divider_below", False)

                updated_categories.append({
                    "column": col_name,
                    "label": label_val,
                    "row_type": row_type,
                    "max_marks": max_marks,
                    "weight": None,
                    "comments_column": comments_col,
                    "type": cat_type,
                    "subdivision": cat_subdivision,
                    "rubric_marks": rubric_marks,
                    "unit": unit_val,
                    "exclude_radar": exclude_radar,
                    "divider_below": divider_below,
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

        # Filter uploaded_data to remove rows missing student ID (e.g. blank rows/headers)
        col_id = mappings["col_student_id"]
        filtered_data = []
        for row in uploaded_data:
            s_id = row.get(col_id)
            if s_id is not None and str(s_id).strip() != "":
                filtered_data.append(row)
        request.session["uploaded_data"] = filtered_data

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
        "category_marks": {"id": "category_marks", "name": "Category Marks", "width": "full", "enabled": True, "own_row": False},
        "feedback": {"id": "feedback", "name": "Feedback Comments", "width": "full", "enabled": True, "own_row": False},
        "general_feedback": {"id": "general_feedback", "name": "General Feedback", "width": "full", "enabled": False, "own_row": False},
        "radar_chart": {"id": "radar_chart", "name": "Radar Chart", "width": "half", "enabled": True, "own_row": False},
        "histogram": {"id": "histogram", "name": "Histogram Chart", "width": "half", "enabled": True, "own_row": False},
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

    # Ensure all layout blocks have 'own_row' defined
    for b in layout:
        if "own_row" not in b:
            b["own_row"] = False
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
                own_row = request.POST.get(f"own_row_{bid}") == "true"
                    
                updated_layout.append({
                    "id": bid,
                    "name": name_map[bid],
                    "width": width,
                    "enabled": enabled,
                    "own_row": own_row
                })
                
        # Save visual row configuration highlights & dividers
        categories = mappings.get("categories", [])
        for cat in categories:
            col = cat["column"]
            row_type_val = request.POST.get(f"row_type_{col}")
            if row_type_val:
                cat["row_type"] = row_type_val
            
            divider_below_val = request.POST.get(f"divider_below_{col}")
            if divider_below_val is not None:
                cat["divider_below"] = (divider_below_val == "1")

        # Reorder categories based on submitted category_order column names
        category_order_str = request.POST.get("category_order", "")
        if category_order_str:
            try:
                order_cols = [s.strip() for s in category_order_str.split("|||") if s.strip()]
                ordered_cats = []
                remaining_cats = list(categories)
                
                for col_name in order_cols:
                    match = next((c for c in remaining_cats if c["column"] == col_name), None)
                    if match:
                        ordered_cats.append(match)
                        remaining_cats.remove(match)
                
                ordered_cats.extend(remaining_cats)
                mappings["categories"] = ordered_cats
            except Exception:
                pass

        show_numeric_grade_bands = request.POST.get("show_numeric_grade_bands") == "true"
        request.session["show_numeric_grade_bands"] = show_numeric_grade_bands

        general_comments = request.POST.get("general_comments", "").strip()
        request.session["general_comments"] = general_comments

        if updated_layout:
            request.session["layout"] = updated_layout
        
        request.session["mappings"] = mappings
        request.session.modified = True
            
        return redirect("generation_success")

    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    categories = mappings["categories"]
    col_overall_mark = mappings.get("col_overall_mark")

    # Filter rows missing student ID
    valid_data = []
    for r in uploaded_data:
        s_id = r.get(col_id)
        if s_id is not None and str(s_id).strip() != "":
            valid_data.append(r)
    uploaded_data = valid_data

    cohort_final_marks, category_averages = build_assessment_cohort_stats(
        uploaded_data,
        categories,
        mappings["degree_level"],
        mappings.get("col_overall_mark"),
        mappings.get("col_group"),
    )

    # Prepare student selection list - only includes students with a final mark
    students_list = []
    for idx, r in enumerate(uploaded_data):
        if col_overall_mark:
            overall_mark = r.get(col_overall_mark)
            if overall_mark is None or str(overall_mark).strip() == "":
                continue
        s_name = get_student_name(r, idx, mappings)
        raw_s_id = r.get(col_id)
        s_id = format_student_id(raw_s_id) if raw_s_id is not None else f"ID-{idx+1}"
        students_list.append({
            "index": idx,
            "name": s_name,
            "id": s_id,
        })

    # Read selected student index from query param
    try:
        preview_student_index = int(request.GET.get("student_index", -1))
    except (ValueError, TypeError):
        preview_student_index = -1

    valid_indices = [s["index"] for s in students_list]
    if preview_student_index not in valid_indices:
        preview_student_index = valid_indices[0] if valid_indices else 0

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
        
    col_id = mappings["col_student_id"]
    col_overall_mark = mappings.get("col_overall_mark")

    # Filter rows missing student ID
    valid_data = []
    for r in uploaded_data:
        s_id = r.get(col_id)
        if s_id is not None and str(s_id).strip() != "":
            valid_data.append(r)
    uploaded_data = valid_data
        
    layout = request.session.get("layout")
    layout = ensure_layout_defaults(layout, session=request.session)
        
    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]
    categories = mappings["categories"]

    cohort_final_marks, category_averages = build_assessment_cohort_stats(
        uploaded_data,
        mappings["categories"],
        mappings["degree_level"],
        mappings.get("col_overall_mark"),
        mappings.get("col_group"),
    )
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, student_row in enumerate(uploaded_data):
            # Skip if missing final mark
            if col_overall_mark:
                overall_mark = student_row.get(col_overall_mark)
                if overall_mark is None or str(overall_mark).strip() == "":
                    continue

            student_name = get_student_name(student_row, idx, mappings)
            raw_student_id = student_row.get(col_id)
            student_id = format_student_id(raw_student_id) if raw_student_id is not None else f"ID-{idx+1}"
            
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


def generation_success(request):
    """
    Step 2.7: Generation Success Landing Page
    Shows confirmation stats and holds download buttons for the ZIP and Email Sending Utility.
    """
    uploaded_data = request.session.get("uploaded_data")
    mappings = request.session.get("mappings")
    if not uploaded_data or not mappings:
        return redirect("upload_file")
        
    col_id = mappings["col_student_id"]
    col_overall_mark = mappings.get("col_overall_mark")

    # Filter rows missing student ID or (if mapped) overall mark
    valid_data = []
    for r in uploaded_data:
        s_id = r.get(col_id)
        if s_id is None or str(s_id).strip() == "":
            continue
        if col_overall_mark:
            overall_mark = r.get(col_overall_mark)
            if overall_mark is None or str(overall_mark).strip() == "":
                continue
        valid_data.append(r)
    uploaded_data = valid_data
    student_count = len(uploaded_data)
    return render(request, "assessment_feedback/success.html", {
        "student_count": student_count,
    })


def download_email_xlsm(request):
    """
    Step 2.8: XLSM Email Sending Utility Generator View
    Pre-populates a macro-enabled Excel sheet from the template in resources
    with student numbers, names, and exact matching feedback filenames.
    """
    from pathlib import Path
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse

    uploaded_data = request.session.get("uploaded_data")
    mappings = request.session.get("mappings")
    if not uploaded_data or not mappings:
        return redirect("upload_file")

    col_id = mappings["col_student_id"]
    col_overall_mark = mappings.get("col_overall_mark")

    # Filter rows missing student ID
    valid_data = []
    for r in uploaded_data:
        s_id = r.get(col_id)
        if s_id is not None and str(s_id).strip() != "":
            valid_data.append(r)
    uploaded_data = valid_data

    col_name = mappings["col_student_name"]
    col_id = mappings["col_student_id"]

    template_path = Path(__file__).parent / "resources" / "_send_emails.xlsm"
    
    try:
        wb = openpyxl.load_workbook(template_path, keep_vba=True)
    except Exception as e:
        return HttpResponse(f"Error loading template: {str(e)}", status=500)

    ws = wb['Students'] if 'Students' in wb.sheetnames else wb.active

    # Clean existing data rows under header starting from Row 2
    if ws.max_row > 1:
        for r in range(2, ws.max_row + 1):
            for c in range(1, 4):
                ws.cell(row=r, column=c, value=None)

    # Populate rows
    row_idx = 2
    for idx, student_row in enumerate(uploaded_data):
        # Skip if missing final mark
        if col_overall_mark:
            overall_mark = student_row.get(col_overall_mark)
            if overall_mark is None or str(overall_mark).strip() == "":
                continue

        student_name = get_student_name(student_row, idx, mappings)
        raw_student_id = student_row.get(col_id)
        student_id = format_student_id(raw_student_id) if raw_student_id is not None else f"ID-{idx+1}"
        
        if not student_name and not student_id:
            continue
            
        filename = f"{slugify(student_id)}_{slugify(student_name)}.html"
        
        ws.cell(row=row_idx, column=1, value=student_id)
        ws.cell(row=row_idx, column=2, value=student_name)
        ws.cell(row=row_idx, column=3, value=filename)
        row_idx += 1

    module_code = mappings.get("module_code", "").strip() or "COMP101"
    module_title = mappings.get("module_title", "").strip() or "Module Performance"
    assessment_component = mappings.get("assessment_component", "").strip()
    assessment_title = mappings.get("assessment_title", "").strip() or "Feedback Report"

    # J13: <Module code> <Module Name> - <Assessment component> Feedback
    subject_parts = [module_code, module_title]
    subject_text = " ".join([p for p in subject_parts if p])
    if assessment_component:
        subject_text = f"{subject_text} - {assessment_component} Feedback"
    else:
        subject_text = f"{subject_text} - Feedback"
    ws['J13'] = subject_text.replace("  ", " ").strip()

    # J16: <Module code> <Assessment component> <Assessment Name> Feedback
    header_parts = [module_code, assessment_component, assessment_title, "Feedback"]
    header_text = " ".join([p for p in header_parts if p])
    ws['J16'] = header_text.replace("  ", " ").strip()

    # J19: Feedback for <Assessment component> <Assessment Name> can be found attached to this email.
    text_parts = [assessment_component, assessment_title]
    text_sub = " ".join([p for p in text_parts if p])
    ws['J19'] = f"Feedback for {text_sub} can be found attached to this email.".replace("  ", " ").strip()

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.ms-excel.sheet.macroEnabled.12'
    )
    response['Content-Disposition'] = 'attachment; filename="send_feedback.xlsm"'
    return response
