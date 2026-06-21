import io
import re
import math
import zipfile
import json
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse

from core.mcrf_parser import parse_mcrf_workbook, is_assessment_component_column
from core.utils.marks import component_percentage, round_mark_pct

COMPONENT_CATEGORIES = [
    "Individual CW",
    "Exam",
    "Presentation",
    "Group CW",
    "Portfolio"
]


def auto_detect_component_category(column_name):
    """Auto-detects component category based on keywords in Excel column header."""
    if not column_name:
        return "Individual CW"
    col_lower = column_name.lower()
    if re.search(r'\bexam(s|inations?)?\b|\bex\d?\b|\btest(s)?\b|\bquiz(zes)?\b', col_lower):
        return "Exam"
    if re.search(r'\bpresentations?\b|\bpres\b|\bvivas?\b|\btalks?\b', col_lower):
        return "Presentation"
    if re.search(r'\bgroups?\b|\bgp\b|\bteams?\b', col_lower):
        return "Group CW"
    if re.search(r'\bportfolios?\b|\bport\b', col_lower):
        return "Portfolio"
    return "Individual CW"


def infer_module_level(module_code):
    """Infers module level from the first digit of the numeric part of code."""
    if not module_code:
        return 4
    numeric_match = re.search(r'\d+', module_code)
    if numeric_match:
        digits = numeric_match.group(0)
        if digits:
            first_digit = digits[0]
            try:
                val = int(first_digit)
                if 3 <= val <= 7:
                    return val
            except ValueError:
                pass
    return 4


def extract_student_id(row):
    """Finds the student ID / Username column value in an Excel row."""
    for key, val in row.items():
        key_lower = str(key).lower()
        if any(kw in key_lower for kw in ["student id", "student number", "student no", "username"]):
            if val is not None and str(val).strip():
                return str(val).strip()
    for key, val in row.items():
        key_lower = str(key).lower()
        if "student" in key_lower or "id" in key_lower:
            if val is not None and str(val).strip():
                return str(val).strip()
    return None


def auto_detect_year_from_filename(filename):
    """Extracts a year like 2024/25, 2024_25, 2024-25, or 2024 from a filename."""
    # Matches e.g. 2024/25, 2024-25, 2024_25
    m1 = re.search(r'(?<![a-zA-Z0-9])(20\d{2})[-/_](\d{2})(?![a-zA-Z0-9])', filename)
    if m1:
        return f"{m1.group(1)}/{m1.group(2)}"
    # Matches 4-digit years like 2022
    m2 = re.search(r'(?<![a-zA-Z0-9])(20\d{2})(?![a-zA-Z0-9])', filename)
    if m2:
        val = int(m2.group(1))
        return f"{val}/{str(val + 1)[-2:]}"
    # Matches e.g. 24-25
    m3 = re.search(r'(?<![a-zA-Z0-9])(\d{2})[-/_](\d{2})(?![a-zA-Z0-9])', filename)
    if m3:
        try:
            yr_start = int(m3.group(1))
            yr_end = int(m3.group(2))
            if yr_end == yr_start + 1:
                return f"20{yr_start}/{yr_end:02d}"
        except ValueError:
            pass
    return ""
def extract_occurrence_code(occ_str, filename=""):
    """Extracts occurrence code like BNN, FNN, or other 3-4 letter uppercase acronyms.
    """
    if not occ_str and not filename:
        return ""
    # Try to find codes ending in NN first (strong indicator)
    for text in [occ_str, filename]:
        if not text:
            continue
        m = re.search(r'(?<![a-zA-Z0-9])([A-Z]{1,4}NN)(?![a-zA-Z0-9])', text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
            
    # Fallback to general 3-4 letter uppercase words
    # but ignore common words that might appear in occurrence field
    ignore_words = {"MCRF", "YEAR", "L7", "LVL", "EXAM", "MARK"}
    for text in [occ_str, filename]:
        if not text:
            continue
        matches = re.findall(r'(?<![a-zA-Z0-9])([A-Z]{3,4})(?![a-zA-Z0-9])', text)
        for match in matches:
            match_upper = match.upper()
            if match_upper not in ignore_words:
                return match_upper
                
    return ""

# Helper to normalize a year string to YYYY/YY format (e.g. "2025/26")
def normalize_year(year_str):
    """Normalises academic year string to YYYY/YY format (e.g., '2025/26').
    If format is invalid or cannot be parsed, returns the original trimmed string.
    """
    if not year_str:
        return ""
    year_str = str(year_str).strip()
    # Matches e.g., 2024/25, 2024-25, 2024_25 or 2024/5, 2024-5
    m = re.search(r'(\d{4})[-/_](\d{1,2})', year_str)
    if m:
        start_yr = int(m.group(1))
        end_yr_part = m.group(2)
        if len(end_yr_part) == 1:
            end_yr = (start_yr + 1) % 100
        else:
            try:
                end_yr = int(end_yr_part) % 100
            except ValueError:
                end_yr = (start_yr + 1) % 100
        return f"{start_yr}/{end_yr:02d}"
    
    # Matches a single 4 digit year like '2025'
    m2 = re.search(r'(\d{4})', year_str)
    if m2:
        start_yr = int(m2.group(1))
        end_yr = (start_yr + 1) % 100
        return f"{start_yr}/{end_yr:02d}"
        
    return year_str

# Helper to convert a year string like "2022/23" to an integer start year
def year_to_int(year_str):
    """Extract the starting year as an integer from a year string.
    Returns None if the format is unrecognised.
    """
    if not year_str:
        return None
    normalized = normalize_year(year_str)
    m = re.search(r'(\d{4})', normalized)
    if m:
        return int(m.group(1))
    return None

def get_level_4_equivalent_year(records):
    """Calculates the Level 4 equivalent academic year for a student based on their records.
    This serves as the 'Graduation/Target Cohort' key.
    """
    if not records:
        return ""
    # 1. Check if they have a Level 4 record
    l4_records = [rec for rec in records.values() if rec.get('level') == 4]
    if l4_records:
        return min(rec['year'] for rec in l4_records)
    
    # 2. Check Level 3 records
    l3_records = [rec for rec in records.values() if rec.get('level') == 3]
    if l3_records:
        start_l3_yr = min(rec['year'] for rec in l3_records)
        start_l3_int = year_to_int(start_l3_yr)
        if start_l3_int:
            return f"{start_l3_int + 1}/{str(start_l3_int + 2)[-2:]}"
            
    # 3. Check Level 5 records
    l5_records = [rec for rec in records.values() if rec.get('level') == 5]
    if l5_records:
        start_l5_yr = min(rec['year'] for rec in l5_records)
        start_l5_int = year_to_int(start_l5_yr)
        if start_l5_int:
            return f"{start_l5_int - 1}/{str(start_l5_int)[-2:]}"
            
    # 4. Check Level 6 records
    l6_records = [rec for rec in records.values() if rec.get('level') == 6]
    if l6_records:
        start_l6_yr = min(rec['year'] for rec in l6_records)
        start_l6_int = year_to_int(start_l6_yr)
        if start_l6_int:
            return f"{start_l6_int - 2}/{str(start_l6_int - 1)[-2:]}"
            
    # 5. Check Level 7 records
    l7_records = [rec for rec in records.values() if rec.get('level') == 7]
    if l7_records:
        start_l7_yr = min(rec['year'] for rec in l7_records)
        start_l7_int = year_to_int(start_l7_yr)
        if start_l7_int:
            return f"{start_l7_int - 3}/{str(start_l7_int - 2)[-2:]}"
            
    # Fallback to the minimum year of any record
    return min(rec['year'] for rec in records.values())

def filter_students_by_cohort_year(students_meta, filter_type, single_year=None, start_year=None, end_year=None):
    """Filters students based on their Level 4 equivalent academic year.
    Returns a set of student_ids that match the filter criteria.
    """
    all_student_ids = list(students_meta.keys())
    if filter_type == 'all' or not filter_type:
        return set(all_student_ids)
        
    filtered_ids = set()
    target_single = year_to_int(single_year)
    target_start = year_to_int(start_year)
    target_end = year_to_int(end_year)
    
    for stud_id, records in students_meta.items():
        l4_equiv = get_level_4_equivalent_year(records)
        equiv_int = year_to_int(l4_equiv)
        if not equiv_int:
            continue
            
        if filter_type == 'single':
            if equiv_int == target_single:
                filtered_ids.add(stud_id)
        elif filter_type == 'range':
            s = target_start
            e = target_end
            if s is not None and e is not None:
                if s > e:
                    s, e = e, s
                if s <= equiv_int <= e:
                    filtered_ids.add(stud_id)
                    
    return filtered_ids

def filter_students_by_occurrence(students_meta, occurrence_filter):
    """Filters students based on whether they have at least one Level 7 record
    matching the specified occurrence code (e.g. BNN, FNN).
    Returns a set of student_ids.
    """
    all_student_ids = list(students_meta.keys())
    if not occurrence_filter or occurrence_filter == 'all':
        return set(all_student_ids)
        
    filtered_ids = set()
    target_occ = str(occurrence_filter).strip().upper()
    for stud_id, records in students_meta.items():
        # Check if they have a Level 7 record with the target occurrence
        has_matching_occ = any(
            rec.get('level') == 7 and str(rec.get('occurrence', '')).strip().upper() == target_occ
            for rec in records.values()
        )
        if has_matching_occ:
            filtered_ids.add(stud_id)
            
    return filtered_ids

def pearson_correlation(x, y):
    """Computes the Pearson correlation coefficient between two lists of numbers."""
    n = len(x)
    if n < 3:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    diff_x = [val - mean_x for val in x]
    diff_y = [val - mean_y for val in y]
    num = sum(dx * dy for dx, dy in zip(diff_x, diff_y))
    den_x = sum(dx ** 2 for dx in diff_x)
    den_y = sum(dy ** 2 for dy in diff_y)
    if den_x == 0 or den_y == 0:
        return None
    return num / math.sqrt(den_x * den_y)


def longitudinal_upload(request):
    """Handles upload of multiple spreadsheets/PDFs for longitudinal analytics."""
    if request.method == "POST":
        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            return render(request, "longitudinal_analytics/upload.html", {"error": "Please select one or more files to upload."})

        parsed_modules = []
        errors = []

        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            if filename.endswith('.zip'):
                try:
                    with zipfile.ZipFile(uploaded_file) as z:
                        for name in z.namelist():
                            if name.endswith(('.xls', '.xlsx', '.pdf')) and not name.startswith('__MACOSX/') and not name.split('/')[-1].startswith('.'):
                                try:
                                    with z.open(name) as f:
                                        file_content = f.read()
                                        file_like = io.BytesIO(file_content)
                                        file_like.name = name
                                        headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(file_like)
                                        parsed_modules.append({
                                            'filename': name.split('/')[-1],
                                            'headers': headers,
                                            'data_rows': data_rows,
                                            'is_mcrf': is_mcrf,
                                            'module_info': module_info
                                        })
                                except Exception as e:
                                    errors.append(f"Failed to parse '{name}' inside zip: {str(e)}")
                except Exception as e:
                    errors.append(f"Failed to extract zip file '{filename}': {str(e)}")
            elif filename.endswith(('.xls', '.xlsx', '.pdf')):
                try:
                     headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(uploaded_file)
                     parsed_modules.append({
                         'filename': filename,
                         'headers': headers,
                         'data_rows': data_rows,
                         'is_mcrf': is_mcrf,
                         'module_info': module_info
                     })
                except Exception as e:
                     errors.append(f"Failed to parse '{filename}': {str(e)}")
            else:
                errors.append(f"Unsupported file format for '{filename}'. Only .xls, .xlsx, .pdf, and .zip files are supported.")

        if errors:
            return render(request, "longitudinal_analytics/upload.html", {"error": " ".join(errors)})

        if not parsed_modules:
            return render(request, "longitudinal_analytics/upload.html", {"error": "No valid MCRF spreadsheets or PDFs were found."})

        modules_data = []
        for pm in parsed_modules:
            headers = pm['headers']
            data_rows = pm['data_rows']
            module_info = pm['module_info']
            is_mcrf = pm.get('is_mcrf', False)
            filename = pm['filename']

            # Extract component column metadata
            components = []
            for h in headers:
                if is_assessment_component_column(h):
                    components.append({
                        "column": h,
                        "max_marks": 100,
                        "weight": 0,
                        "type": "numeric"
                    })

            # Detect weights if MCRF
            has_explicit_weights = False
            for comp in components:
                weight_match = re.search(r'(\d+)\s*%', comp["column"])
                if weight_match:
                    comp["weight"] = int(weight_match.group(1))
                    has_explicit_weights = True

            if not has_explicit_weights and components:
                num_comps = len(components)
                even_weight = 100 // num_comps
                for idx, comp in enumerate(components):
                    if idx == num_comps - 1:
                        comp["weight"] = 100 - (even_weight * (num_comps - 1))
                    else:
                        comp["weight"] = even_weight

            # Compile raw student rows
            raw_rows = []
            comp_names_map = module_info.get("comp_names_map", {})
            for row in data_rows:
                student_id = extract_student_id(row)
                if not student_id:
                    continue

                row_comp_scores = {}
                overall_mark_weighted = 0.0
                for comp in components:
                    pct = component_percentage(row, comp)
                    row_comp_scores[comp["column"]] = pct
                    overall_mark_weighted += (pct * comp["weight"]) / 100.0

                raw_rows.append({
                    "student_id": student_id,
                    "component_scores": row_comp_scores,
                    "overall_mark": round_mark_pct(overall_mark_weighted)
                })

            # Process component categories
            components_data = []
            for comp in components:
                col_name = comp["column"]
                description = ""
                code_match = re.search(r'\b(\d{1,3}|CW\d|EX\d|EXAM\d?)\b', col_name, re.IGNORECASE)
                if code_match:
                    code = code_match.group(1)
                    s = str(code).strip().split('.')[0]
                    code_norm = f"{int(s):03d}" if s.isdigit() else s.upper()
                    description = comp_names_map.get(code_norm, "")

                search_str = f"{col_name} - {description}" if description else col_name
                components_data.append({
                    "column": col_name,
                    "weight": comp["weight"],
                    "detected_category": auto_detect_component_category(search_str)
                })

            # Module details
            code = module_info.get("module_code", "")
            if not code:
                fn_clean = filename.rsplit('.', 1)[0]
                code_match = re.match(r'^([A-Z]{2,6}\d{3,5}[A-Z]?)', fn_clean, re.IGNORECASE)
                code = code_match.group(1).upper() if code_match else fn_clean.upper()

            title = module_info.get("module_title", "") or filename.rsplit('.', 1)[0]
            detected_level = infer_module_level(code)
            detected_year = normalize_year(module_info.get("year", "") or auto_detect_year_from_filename(filename) or "2024/25")
            
            # Detect occurrence code for Level 7 modules
            detected_occurrence = ""
            if detected_level == 7:
                detected_occurrence = extract_occurrence_code(module_info.get("occurrence", ""), filename)

            modules_data.append({
                'filename': filename,
                'module_code': code,
                'module_title': title,
                'is_mcrf': is_mcrf,
                'detected_level': detected_level,
                'detected_credits': module_info.get("detected_credits", 20),
                'detected_year': detected_year,
                'detected_occurrence': detected_occurrence,
                'components': components_data,
                'raw_rows': raw_rows
            })

        modules_data.sort(key=lambda x: x['module_code'])
        request.session['longitudinal_uploaded_modules'] = modules_data
        request.session.modified = True
        return redirect("longitudinal_confirm")

    return render(request, "longitudinal_analytics/upload.html")


def longitudinal_confirm(request):
    """Presents auto-detected module details and lets tutors confirm/correct mappings and years per file."""
    uploaded_modules = request.session.get('longitudinal_uploaded_modules')
    if not uploaded_modules:
        return redirect("longitudinal_upload")

    error = None

    if request.method == "POST":
        confirmed_modules = []
        occ_handle_bulk = request.POST.get("occ_handle_bulk", "merge").strip().lower()
        for idx, m in enumerate(uploaded_modules):
            code = request.POST.get(f"code_{idx}", "").strip()
            title = request.POST.get(f"title_{idx}", "").strip()
            year = normalize_year(request.POST.get(f"year_{idx}", "").strip())
            try:
                level = int(request.POST.get(f"level_{idx}", 4))
            except (ValueError, TypeError):
                level = 4

            # Handle occurrence splitting/merging for Level 7 modules
            occurrence = m.get('detected_occurrence', '')
            occ_handle = "merge"
            if level == 7 and occurrence:
                occ_handle = occ_handle_bulk
                if occ_handle == "separate":
                    code = f"{code}-{occurrence}"

            try:
                credits_val = int(request.POST.get(f"credits_{idx}", 20))
            except (ValueError, TypeError):
                credits_val = 20

            if not code or not title or not year:
                error = "Module Code, Title, and Academic Year are required for all files."
                break

            # Recalculate weights
            processed_components = []
            total_weight = 0
            for comp_idx, comp in enumerate(m.get('components', [])):
                cat = request.POST.get(f"comp_cat_{idx}_{comp_idx}", "Individual CW").strip()
                if cat not in COMPONENT_CATEGORIES:
                    cat = "Individual CW"
                try:
                    weight = int(request.POST.get(f"comp_weight_{idx}_{comp_idx}", 0))
                except (ValueError, TypeError):
                    weight = 0
                total_weight += weight
                processed_components.append({
                    "column": comp["column"],
                    "weight": weight,
                    "category": cat
                })

            if len(processed_components) > 0 and total_weight != 100 and total_weight != 0:
                error = f"Assessment component weights for module {code} must sum to exactly 100% or 0% (currently {total_weight}%)."
                break

            # Re-compile student overall marks
            updated_raw_rows = []
            for student in m.get('raw_rows', []):
                overall_mark_weighted = 0.0
                for comp in processed_components:
                    pct = student["component_scores"].get(comp["column"], 0.0)
                    overall_mark_weighted += (pct * comp["weight"]) / 100.0

                updated_raw_rows.append({
                    "student_id": student["student_id"],
                    "component_scores": student["component_scores"],
                    "overall_mark": round_mark_pct(overall_mark_weighted)
                })

            confirmed_modules.append({
                'filename': m['filename'],
                'module_code': code,
                'module_title': title,
                'is_mcrf': m['is_mcrf'],
                'level': level,
                'credits': credits_val,
                'year': year,
                'occurrence': occurrence,
                'occ_handle': occ_handle,
                'components': processed_components,
                'raw_rows': updated_raw_rows
            })

        if not error:
            request.session['longitudinal_confirmed_data'] = confirmed_modules
            request.session.modified = True
            return redirect("longitudinal_dashboard")

    has_level_7_occurrences = any(m.get('detected_level') == 7 and m.get('detected_occurrence') for m in uploaded_modules)
    return render(request, "longitudinal_analytics/confirm.html", {
        "modules": uploaded_modules,
        "has_level_7_occurrences": has_level_7_occurrences,
        "error": error
    })


def longitudinal_dashboard(request):
    """Calculates aggregates across years/modules and renders the Chart.js analysis dashboard."""
    raw_confirmed_modules = request.session.get('longitudinal_confirmed_data')
    if not raw_confirmed_modules:
        return redirect("longitudinal_upload")
    
    # Normalize year strings to heal any legacy/session data
    for m in raw_confirmed_modules:
        if 'year' in m:
            m['year'] = normalize_year(m['year'])
    
    # Apply global cohort year filter based on GET parameters (matches against Level 4 equivalent entry year)
    filter_type = request.GET.get('filter_type', 'all')
    single_year = request.GET.get('single_year')
    start_year = request.GET.get('start_year')
    end_year = request.GET.get('end_year')
    try:
        non_sub_threshold = int(request.GET.get('non_sub_threshold', 20))
    except (ValueError, TypeError):
        non_sub_threshold = 20
    
    # 1. Collate student marks across ALL uploaded data to correctly define their baseline cohort
    students_unfiltered = {}  # student_id -> { module_code: mark }
    students_meta = {}        # student_id -> { module_code: { mark, level, year, occurrence } }

    for m in raw_confirmed_modules:
        code = m['module_code']
        lvl = m['level']
        yr = m['year']
        occ = m.get('occurrence', '')
        is_pass_fail = (sum(comp['weight'] for comp in m.get('components', [])) == 0) if m.get('components') else False
        for row in m['raw_rows']:
            stud_id = row['student_id']
            if not stud_id:
                continue
            if stud_id not in students_unfiltered:
                students_unfiltered[stud_id] = {}
            if stud_id not in students_meta:
                students_meta[stud_id] = {}
            students_unfiltered[stud_id][code] = row['overall_mark']
            students_meta[stud_id][code] = {
                'mark': row['overall_mark'],
                'level': lvl,
                'year': yr,
                'occurrence': occ,
                'is_pass_fail': is_pass_fail
            }

    # Filter students based on cohort selection
    filtered_student_ids = filter_students_by_cohort_year(students_meta, filter_type, single_year, start_year, end_year)

    students = {sid: marks for sid, marks in students_unfiltered.items() if sid in filtered_student_ids}

    # Restrict modules list to those that have records for our filtered student set
    active_module_codes = set()
    for sid in filtered_student_ids:
        active_module_codes.update(students_unfiltered[sid].keys())
    confirmed_modules = [m for m in raw_confirmed_modules if m['module_code'] in active_module_codes]

    # 2. Correlation Matrix
    def sort_key_for_module(m_code):
        for m in confirmed_modules:
            if m['module_code'] == m_code:
                return (m['level'], m_code)
        return (9, m_code)

    module_codes = sorted(list({m['module_code'] for m in confirmed_modules}), key=sort_key_for_module)
    matrix_data = []  # list of rows: each row is [mod_code, [cells]]

    for m1 in module_codes:
        row_cells = []
        for m2 in module_codes:
            if m1 == m2:
                row_cells.append({
                    "coef": 1.0, 
                    "coef_abs": 1.0,
                    "n": len([s for s in students.values() if m1 in s]), 
                    "is_diagonal": True,
                    "mod1": m1,
                    "mod2": m2
                })
            else:
                marks_x = []
                marks_y = []
                for s in students.values():
                    if m1 in s and m2 in s:
                        val_x = s[m1]
                        val_y = s[m2]
                        if val_x >= non_sub_threshold and val_y >= non_sub_threshold:
                            marks_x.append(val_x)
                            marks_y.append(val_y)

                r = pearson_correlation(marks_x, marks_y)
                coef_val = round(r, 2) if r is not None else None
                coef_abs_val = round(abs(r), 2) if r is not None else 0.0
                row_cells.append({
                    "coef": coef_val,
                    "coef_abs": coef_abs_val,
                    "n": len(marks_x),
                    "is_diagonal": False,
                    "mod1": m1,
                    "mod2": m2
                })
        matrix_data.append({"module_code": m1, "cells": row_cells})

    # 3. Cohort Progression (Mean mark per level, grouped by entry year/level)
    student_cohorts = {}
    for stud_id in filtered_student_ids:
        records = students_meta[stud_id]
        min_lvl = min(rec['level'] for rec in records.values())
        min_lvl_records = [rec for rec in records.values() if rec['level'] == min_lvl]
        start_year = min(rec['year'] for rec in min_lvl_records)
        student_cohorts[stud_id] = {
            'cohort_name': f"Entered L{min_lvl} in {start_year}",
            'start_level': min_lvl,
            'start_year': start_year
        }

    cohort_averages = {}
    for stud_id in filtered_student_ids:
        records = students_meta[stud_id]
        cohort_name = student_cohorts[stud_id]['cohort_name']
        if cohort_name not in cohort_averages:
            cohort_averages[cohort_name] = {}

        student_level_marks = {}
        for rec in records.values():
            if rec.get('is_pass_fail'):
                continue
            lvl = rec['level']
            if lvl not in student_level_marks:
                student_level_marks[lvl] = []
            student_level_marks[lvl].append(rec['mark'])

        for lvl, marks in student_level_marks.items():
            if not marks:
                continue
            if lvl not in cohort_averages[cohort_name]:
                cohort_averages[cohort_name][lvl] = []
            cohort_averages[cohort_name][lvl].append(sum(marks) / len(marks))

    cohort_progression_data = {}
    for cname, lvl_data in cohort_averages.items():
        cohort_size = sum(1 for stud_id, info in student_cohorts.items() if info['cohort_name'] == cname)
        # Only display cohorts with at least 2 students to keep charts clean
        if cohort_size < 2:
            continue
        cohort_progression_data[cname] = {}
        for lvl in [3, 4, 5, 6, 7]:
            if lvl in lvl_data:
                cohort_progression_data[cname][lvl] = round(sum(lvl_data[lvl]) / len(lvl_data[lvl]), 1)
            else:
                cohort_progression_data[cname][lvl] = None

    # 4. Cohort Transitions & Drops
    transitions = ["L3->L4", "L4->L5", "L5->L6", "L6->L7"]
    transition_counts = {
        t: {"improving": 0, "stable": 0, "declining": 0, "total": 0, "mean_diff": 0.0, "diffs": []}
        for t in transitions
    }

    for stud_id in filtered_student_ids:
        records = students_meta[stud_id]
        student_level_marks = {}
        for rec in records.values():
            if rec.get('is_pass_fail'):
                continue
            lvl = rec['level']
            if lvl not in student_level_marks:
                student_level_marks[lvl] = []
            student_level_marks[lvl].append(rec['mark'])

        student_level_avgs = {lvl: sum(m) / len(m) for lvl, m in student_level_marks.items() if m}

        for lvl in [3, 4, 5, 6]:
            if lvl in student_level_avgs and (lvl + 1) in student_level_avgs:
                diff = student_level_avgs[lvl + 1] - student_level_avgs[lvl]
                t_key = f"L{lvl}->L{lvl+1}"
                transition_counts[t_key]["diffs"].append(diff)
                if diff >= 3:
                    transition_counts[t_key]["improving"] += 1
                elif diff <= -3:
                    transition_counts[t_key]["declining"] += 1
                else:
                    transition_counts[t_key]["stable"] += 1
                transition_counts[t_key]["total"] += 1

    largest_drop_transition = None
    largest_drop_val = 0.0

    for t in transitions:
        diffs = transition_counts[t]["diffs"]
        if diffs:
            mean_diff = sum(diffs) / len(diffs)
            transition_counts[t]["mean_diff"] = round(mean_diff, 1)
            if mean_diff < largest_drop_val:
                largest_drop_val = mean_diff
                largest_drop_transition = t
        else:
            transition_counts[t]["mean_diff"] = 0.0

    # 5. Entry Route Analysis (L3 records vs Direct Entrants)
    entry_route_data = {
        'levels': [3, 4, 5, 6, 7],
        'l3_entrants': [],
        'direct_entrants': []
    }

    l3_entrant_ids = set()
    direct_entrant_ids = set()
    for stud_id in filtered_student_ids:
        records = students_meta[stud_id]
        has_l3 = any(rec['level'] == 3 for rec in records.values())
        if has_l3:
            l3_entrant_ids.add(stud_id)
        else:
            direct_entrant_ids.add(stud_id)

    for lvl in [3, 4, 5, 6, 7]:
        l3_marks = []
        direct_marks = []

        for stud_id in l3_entrant_ids:
            lvl_records = [rec['mark'] for rec in students_meta[stud_id].values() if rec['level'] == lvl and not rec.get('is_pass_fail')]
            if lvl_records:
                l3_marks.append(sum(lvl_records) / len(lvl_records))

        for stud_id in direct_entrant_ids:
            lvl_records = [rec['mark'] for rec in students_meta[stud_id].values() if rec['level'] == lvl and not rec.get('is_pass_fail')]
            if lvl_records:
                direct_marks.append(sum(lvl_records) / len(lvl_records))

        entry_route_data['l3_entrants'].append(
            round(sum(l3_marks) / len(l3_marks), 1) if l3_marks else None
        )
        entry_route_data['direct_entrants'].append(
            round(sum(direct_marks) / len(direct_marks), 1) if direct_marks else None
        )

    # 6. Predictive Indicators (L3/4 correlating with L6/7)
    pass_fail_module_codes = {
        m['module_code'] for m in confirmed_modules 
        if m.get('components') and sum(comp['weight'] for comp in m['components']) == 0
    }
    early_modules = [m['module_code'] for m in confirmed_modules if m['level'] in [3, 4] and m['module_code'] not in pass_fail_module_codes]
    late_modules = [m['module_code'] for m in confirmed_modules if m['level'] in [5, 6, 7] and m['module_code'] not in pass_fail_module_codes]

    early_late_corrs = []
    for E in early_modules:
        for F in late_modules:
            marks_E = []
            marks_F = []
            for stud_id, recs in students.items():
                if E in recs and F in recs:
                    marks_E.append(recs[E])
                    marks_F.append(recs[F])
            r = pearson_correlation(marks_E, marks_F)
            if r is not None:
                early_late_corrs.append({
                    'early_module': E,
                    'late_module': F,
                    'r': round(r, 2),
                    'n': len(marks_E)
                })

    early_late_corrs.sort(key=lambda x: abs(x['r']), reverse=True)
    top_correlations = early_late_corrs[:5]

    risk_predictors = []
    for E in early_modules:
        total_poor = 0
        failed_later = 0
        for stud_id, recs in students.items():
            if E in recs:
                late_recs = {mcode: mark for mcode, mark in recs.items() if mcode in late_modules}
                if late_recs:
                    if recs[E] < 50:
                        total_poor += 1
                        has_failed_late = any(val < 40 for val in late_recs.values())
                        if has_failed_late:
                            failed_later += 1

        if total_poor >= 3:
            prob = (failed_later / total_poor) * 100.0
            risk_predictors.append({
                'early_module': E,
                'poor_count': total_poor,
                'failed_later_count': failed_later,
                'probability': round(prob, 1)
            })

    risk_predictors.sort(key=lambda x: x['probability'], reverse=True)
    top_risk_predictors = risk_predictors[:5]

    # Convert progression and transition counts to format easily consumed by Chart.js JSON
    chart_transition_data = {
        "labels": transitions,
        "improving": [transition_counts[t]["improving"] for t in transitions],
        "stable": [transition_counts[t]["stable"] for t in transitions],
        "declining": [transition_counts[t]["declining"] for t in transitions]
    }

    # Format cohort lines data for Chart.js
    chart_cohort_lines = []
    colors = ["#4361ee", "#ff006e", "#3a0ca3", "#7209b7", "#4cc9f0", "#ff7a59", "#10b981", "#f59e0b", "#64748b"]
    for idx, (cname, lvl_vals) in enumerate(cohort_progression_data.items()):
        y_vals = [lvl_vals.get(lvl) for lvl in [3, 4, 5, 6, 7]]
        chart_cohort_lines.append({
            "label": cname,
            "data": y_vals,
            "borderColor": colors[idx % len(colors)],
            "backgroundColor": colors[idx % len(colors)],
            "fill": False,
            "tension": 0.1
        })

    # Extract available years for filter UI based on Level 4 equivalent entry years
    available_years = sorted({get_level_4_equivalent_year(recs) for recs in students_meta.values() if recs})
    
    context = {
        "module_codes": module_codes,
        "matrix_data": matrix_data,
        "chart_cohort_lines_json": json.dumps(chart_cohort_lines),
        "chart_transition_json": json.dumps(chart_transition_data),
        "entry_route_json": json.dumps(entry_route_data),
        "top_correlations": top_correlations,
        "top_risk_predictors": top_risk_predictors,
        "largest_drop_transition": largest_drop_transition,
        "largest_drop_val": round(abs(largest_drop_val), 1) if largest_drop_transition else 0.0,
        "available_years": available_years,
        "non_sub_threshold": non_sub_threshold,
    }


    return render(request, "longitudinal_analytics/dashboard.html", context)


def longitudinal_scatter_data(request):
    """Returns JSON points and regression coordinates for selected module codes from the session."""
    confirmed_data = request.session.get('longitudinal_confirmed_data', [])
    
    # Normalize year strings to heal any legacy/session data
    for m in confirmed_data:
        if 'year' in m:
            m['year'] = normalize_year(m['year'])
            
    # Apply same global year filter as dashboard
    filter_type = request.GET.get('filter_type', 'all')
    single_year = request.GET.get('single_year')
    start_year = request.GET.get('start_year')
    end_year = request.GET.get('end_year')
    mod1 = request.GET.get('mod1')
    mod2 = request.GET.get('mod2')

    if not confirmed_data or not mod1 or not mod2:
        return JsonResponse({"error": "Invalid request or session data expired."}, status=400)

    # 1. Collate student marks across ALL modules to find their entry cohort baseline
    students = {}       # student_id -> { module_code: mark }
    students_meta = {}  # student_id -> { module_code: { mark, level, year, occurrence } }
    
    for m in confirmed_data:
        code = m['module_code']
        lvl = m['level']
        yr = m['year']
        occ = m.get('occurrence', '')
        is_pass_fail = (sum(comp['weight'] for comp in m.get('components', [])) == 0) if m.get('components') else False
        for row in m['raw_rows']:
            sid = row['student_id']
            if sid:
                if sid not in students:
                    students[sid] = {}
                if sid not in students_meta:
                    students_meta[sid] = {}
                students[sid][code] = row['overall_mark']
                students_meta[sid][code] = {
                    'mark': row['overall_mark'],
                    'level': lvl,
                    'year': yr,
                    'occurrence': occ,
                    'is_pass_fail': is_pass_fail
                }

    # 2. Filter students based on cohort selection
    filtered_student_ids = filter_students_by_cohort_year(students_meta, filter_type, single_year, start_year, end_year)

    # 3. Build coordinates using filtered student set
    points = []
    for sid in filtered_student_ids:
        recs = students.get(sid, {})
        if mod1 in recs and mod2 in recs:
            points.append({'x': recs[mod1], 'y': recs[mod2]})

    xs = [pt['x'] for pt in points]
    ys = [pt['y'] for pt in points]
    n = len(points)

    regression_line = []
    r_coef = None
    m_slope = 0
    c_intercept = 0

    if n >= 3:
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)

        if den != 0:
            m_slope = num / den
            c_intercept = mean_y - m_slope * mean_x
            min_x = min(xs)
            max_x = max(xs)
            regression_line = [
                {'x': min_x, 'y': round(m_slope * min_x + c_intercept, 1)},
                {'x': max_x, 'y': round(m_slope * max_x + c_intercept, 1)}
            ]
        r_coef = pearson_correlation(xs, ys)

    return JsonResponse({
        "points": points,
        "regression_line": regression_line,
        "r": round(r_coef, 2) if r_coef is not None else None,
        "n": n,
        "mod1": mod1,
        "mod2": mod2
    })
