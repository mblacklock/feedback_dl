import io
import re
import math
import zipfile
import json
import hashlib
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.urls import reverse
from django.conf import settings

from core.mcrf_parser import parse_mcrf_workbook, is_assessment_component_column
from core.utils.marks import build_module_cohort_weighted_finals, component_percentage, round_mark_pct
from core.utils.charts import (
    generate_sparkline_svg,
)


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


def calculate_module_analytics(scores, level):
    """Computes averages and grade distribution percentage for a module cohort."""
    if not scores:
        return {
            "mean": 0.0,
            "median": 0.0,
            "std_dev": 0.0,
            "max": 0.0,
            "min": 0.0,
            "pct_1st": 0.0,
            "pct_21_above": 0.0,
            "pct_fail": 0.0,
            "cohort_size": 0,
            "score_bins": {
                "absent": 0,
                "bins": [0] * 10
            }
        }
    n = len(scores)
    mean_val = sum(scores) / n
    
    variance = sum((x - mean_val) ** 2 for x in scores) / n
    std_dev = math.sqrt(variance)
    
    sorted_scores = sorted(scores)
    mid = n // 2
    if n % 2 != 0:
        median_val = sorted_scores[mid]
    else:
        median_val = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2.0
    
    is_pg = (level >= 7)
    fail_threshold = 50 if is_pg else 40
    
    fail_count = sum(1 for x in scores if x < fail_threshold)
    first_count = sum(1 for x in scores if x >= 70)
    two_one_above_count = sum(1 for x in scores if x >= 60)

    # Bin scores: absent (exactly 0) and 10% bins from (0, 100]
    absent_count = sum(1 for x in scores if x == 0)
    bins = [0] * 10
    for x in scores:
        if x == 0:
            continue
        if x < 10:
            bins[0] += 1
        elif x < 20:
            bins[1] += 1
        elif x < 30:
            bins[2] += 1
        elif x < 40:
            bins[3] += 1
        elif x < 50:
            bins[4] += 1
        elif x < 60:
            bins[5] += 1
        elif x < 70:
            bins[6] += 1
        elif x < 80:
            bins[7] += 1
        elif x < 90:
            bins[8] += 1
        else:
            bins[9] += 1
        
    return {
        "mean": mean_val,
        "median": median_val,
        "std_dev": std_dev,
        "max": float(max(scores)),
        "min": float(min(scores)),
        "pct_1st": (first_count / n) * 100.0,
        "pct_21_above": (two_one_above_count / n) * 100.0,
        "pct_fail": (fail_count / n) * 100.0,
        "cohort_size": n,
        "score_bins": {
            "absent": absent_count,
            "bins": bins,
        }
    }





def analytics_upload(request):
    """Handles drag-and-drop / select upload for multiple files and/or zip files."""
    if request.method == "POST":
        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            return render(request, "programme_analytics/upload.html", {"error": "Please select one or more files to upload."})

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
            return render(request, "programme_analytics/upload.html", {
                "error": " ".join(errors)
            })

        if not parsed_modules:
            return render(request, "programme_analytics/upload.html", {
                "error": "No valid MCRF spreadsheets or PDFs were found in the uploaded files."
            })

        modules_data = []
        for pm in parsed_modules:
            headers = pm['headers']
            data_rows = pm['data_rows']
            module_info = pm['module_info']
            is_mcrf = pm.get('is_mcrf', False)
            
            components = []
            for h in headers:
                if is_assessment_component_column(h):
                    components.append({
                        "column": h,
                        "max_marks": 100,
                        "weight": 0,
                        "type": "numeric"
                    })
            
            has_explicit_weights = False
            for comp in components:
                weight_match = re.search(r'(\d+)\s*%', comp["column"])
                if weight_match:
                    comp["weight"] = int(weight_match.group(1))
                    has_explicit_weights = True
            
            if not has_explicit_weights:
                num_comps = len(components)
                if num_comps > 0:
                    even_weight = 100 // num_comps
                    for idx, comp in enumerate(components):
                        if idx == num_comps - 1:
                            comp["weight"] = 100 - (even_weight * (num_comps - 1))
                        else:
                            comp["weight"] = even_weight

            row_data_summary = []
            if components and data_rows:
                scores = build_module_cohort_weighted_finals(data_rows, components)
                # Store component scores
                components_data = []
                comp_names_map = module_info.get("comp_names_map", {})
                for comp in components:
                    col_name = comp["column"]
                    comp_scores = [round_mark_pct(component_percentage(row, comp)) for row in data_rows]
                    
                    # Extract component code and look up descriptive name
                    description = ""
                    code_match = re.search(r'\b(\d{1,3}|CW\d|EX\d|EXAM\d?)\b', col_name, re.IGNORECASE)
                    if code_match:
                        code = code_match.group(1)
                        s = str(code).strip().split('.')[0]
                        code_norm = f"{int(s):03d}" if s.isdigit() else s.upper()
                        description = comp_names_map.get(code_norm, "")
                    
                    # Scan both column header and MCRF header description
                    search_str = f"{col_name} - {description}" if description else col_name
                    
                    components_data.append({
                        "column": col_name,
                        "weight": comp["weight"],
                        "scores": comp_scores,
                        "detected_category": auto_detect_component_category(search_str)
                    })
                
                # Gather component percentage scores per row for recalculation on confirmation page
                for row in data_rows:
                    row_comp_scores = {}
                    for comp in components:
                        row_comp_scores[comp["column"]] = component_percentage(row, comp)
                    
                    row_data_summary.append({
                        "student_id": extract_student_id(row),
                        "component_scores": row_comp_scores
                    })
            else:
                scores = []
                components_data = []

            # Infer module details
            code = module_info.get("module_code", "")
            if not code:
                fn_clean = pm['filename'].rsplit('.', 1)[0]
                code_match = re.match(r'^([A-Z]{2,6}\d{3,5}[A-Z]?)', fn_clean, re.IGNORECASE)
                if code_match:
                    code = code_match.group(1).upper()
                else:
                    code = fn_clean.upper()

            title = module_info.get("module_title", "")
            if not title:
                title = pm['filename'].rsplit('.', 1)[0]

            detected_level = infer_module_level(code)

            modules_data.append({
                'filename': pm['filename'],
                'module_code': code,
                'module_title': title,
                'is_mcrf': is_mcrf,
                'detected_level': detected_level,
                'detected_credits': module_info.get("detected_credits", 20),
                'scores': scores,
                'year': module_info.get("year", ""),
                'period': module_info.get("period", ""),
                'occurrence': module_info.get("occurrence", ""),
                'components': components_data,
                'comp_names_map': module_info.get("comp_names_map", {}),
                'row_data_summary': row_data_summary,
            })

        # Sort modules by code alphabetically
        modules_data.sort(key=lambda x: x['module_code'])

        request.session['analytics_uploaded_modules'] = modules_data
        request.session.modified = True
        return redirect("analytics_confirm")

    return render(request, "programme_analytics/upload.html")


def analytics_confirm(request):
    """Presents auto-detected details for mapping/level confirmation and metadata setup."""
    uploaded_modules = request.session.get('analytics_uploaded_modules')
    if not uploaded_modules:
        return redirect("analytics_upload")

    error = None
    default_year = ""
    for m in uploaded_modules:
        if m.get('year'):
            default_year = m['year']
            break

    if request.method == "POST":
        programme_name = request.POST.get("programme_name", "").strip()
        academic_year = request.POST.get("academic_year", "").strip()

        if not programme_name or not academic_year:
            error = "Programme Name and Academic Year are required."
        else:
            confirmed_modules = []
            for idx, m in enumerate(uploaded_modules):
                code = request.POST.get(f"code_{idx}", "").strip()
                title = request.POST.get(f"title_{idx}", "").strip()
                try:
                    level = int(request.POST.get(f"level_{idx}", 4))
                except (ValueError, TypeError):
                    level = 4

                try:
                    credits = int(request.POST.get(f"credits_{idx}", 20))
                except (ValueError, TypeError):
                    credits = 20

                if not code or not title:
                    error = "Module Code and Module Title cannot be empty."
                    break

                # Process components and their selected normalized categories and weights
                processed_components = []
                total_weight = 0
                for comp_idx, comp in enumerate(m.get('components', [])):
                    cat = request.POST.get(f"comp_cat_{idx}_{comp_idx}", comp.get("category", comp.get("detected_category", "Individual CW"))).strip()
                    if cat not in COMPONENT_CATEGORIES:
                        cat = "Individual CW"
                    try:
                        weight = int(request.POST.get(f"comp_weight_{idx}_{comp_idx}", comp.get("weight", 0)))
                    except (ValueError, TypeError):
                        weight = 0
                    total_weight += weight
                    processed_components.append({
                        "column": comp["column"],
                        "weight": weight,
                        "scores": comp.get("scores", []),
                        "category": cat
                    })

                # Store the user's edits back into the temporary structure in case validation fails
                m['components'] = processed_components
                m['module_code'] = code
                m['module_title'] = title
                m['detected_level'] = level
                m['detected_credits'] = credits

                # Validate total weight sums to 100% or 0% (for pass/fail modules)
                if processed_components and total_weight != 100 and total_weight != 0:
                    error = f"Total component weight for module '{code}' must sum to exactly 100% or 0% (currently {total_weight}%)."
                    break

                # Recalculate module final scores using the new weights
                new_scores = []
                new_student_ids = []
                row_summary = m.get('row_data_summary', [])
                if row_summary:
                    for row in row_summary:
                        row_weighted_pct = 0
                        for comp in processed_components:
                            comp_pct = row["component_scores"].get(comp["column"], 0)
                            row_weighted_pct += (comp_pct * comp["weight"]) / 100
                        final_score = round_mark_pct(row_weighted_pct)
                        new_scores.append(final_score)
                        new_student_ids.append(row.get("student_id"))
                else:
                    new_scores = m.get('scores', [])
                    new_student_ids = m.get('student_ids', [None] * len(new_scores))

                stats = calculate_module_analytics(new_scores, level)

                confirmed_modules.append({
                    'filename': m['filename'],
                    'module_code': code,
                    'module_title': title,
                    'level': level,
                    'credits': credits,
                    'detected_credits': credits,
                    'scores': new_scores,
                    'student_ids': new_student_ids,
                    'mean': stats['mean'],
                    'median': stats['median'],
                    'std_dev': stats['std_dev'],
                    'max': stats['max'],
                    'min': stats['min'],
                    'pct_1st': stats['pct_1st'],
                    'pct_21_above': stats['pct_21_above'],
                    'pct_fail': stats['pct_fail'],
                    'cohort_size': stats['cohort_size'],
                    'components': processed_components,
                    'comp_names_map': m.get('comp_names_map', {}),
                })

            if error:
                # Save modified inputs to the session so they are preserved on re-render
                request.session['analytics_uploaded_modules'] = uploaded_modules
                request.session.modified = True
            else:
                # Group confirmed modules by module_code to merge duplicate occurrences
                grouped = {}
                for cm in confirmed_modules:
                    c_code = cm['module_code']
                    if c_code not in grouped:
                        grouped[c_code] = []
                    grouped[c_code].append(cm)

                merged_confirmed_modules = []
                for c_code, group in grouped.items():
                    if len(group) == 1:
                        merged_confirmed_modules.append(group[0])
                    else:
                        first = group[0]
                        # Join source filenames with comma
                        merged_filenames = ", ".join(dict.fromkeys(g['filename'] for g in group))

                        # Combine all student scores
                        all_scores = []
                        for g in group:
                            all_scores.extend(g['scores'])

                        # Combine all student IDs
                        all_student_ids = []
                        for g in group:
                            all_student_ids.extend(g.get('student_ids', [None] * len(g['scores'])))

                        # Recalculate statistics on the combined cohort
                        stats = calculate_module_analytics(all_scores, first['level'])

                        # Combine components by matching column name
                        components_by_col = {}
                        for g in group:
                            for comp in g.get('components', []):
                                col = comp['column']
                                if col not in components_by_col:
                                    components_by_col[col] = {
                                        "column": col,
                                        "weight": comp["weight"],
                                        "scores": list(comp.get("scores", [])),
                                        "category": comp["category"]
                                    }
                                else:
                                    components_by_col[col]["scores"].extend(comp.get("scores", []))

                        merged_components = list(components_by_col.values())

                        # Combine comp_names_map
                        merged_comp_names_map = {}
                        for g in group:
                            merged_comp_names_map.update(g.get('comp_names_map', {}))

                        merged_confirmed_modules.append({
                            'filename': merged_filenames,
                            'module_code': c_code,
                            'module_title': first['module_title'],
                            'level': first['level'],
                            'credits': first['credits'],
                            'detected_credits': first['detected_credits'],
                            'scores': all_scores,
                            'student_ids': all_student_ids,
                            'mean': stats['mean'],
                            'median': stats['median'],
                            'std_dev': stats['std_dev'],
                            'max': stats['max'],
                            'min': stats['min'],
                            'pct_1st': stats['pct_1st'],
                            'pct_21_above': stats['pct_21_above'],
                            'pct_fail': stats['pct_fail'],
                            'cohort_size': stats['cohort_size'],
                            'components': merged_components,
                            'comp_names_map': merged_comp_names_map,
                        })

                # Sort confirmed modules by module code in case the user edited the codes
                merged_confirmed_modules.sort(key=lambda x: x['module_code'])
                request.session['analytics_confirmed_data'] = {
                    'programme_name': programme_name,
                    'academic_year': academic_year,
                    'modules': merged_confirmed_modules
                }
                request.session.modified = True
                return redirect("analytics_dashboard")

    return render(request, "programme_analytics/confirm.html", {
        "modules": uploaded_modules,
        "default_year": default_year,
        "error": error
    })





def normalize_snapshot(snap):
    """Standardizes keys between session modules and snapshot JSON files."""
    normalized_modules = []
    for m in snap.get('modules', []):
        code = m.get('code') or m.get('module_code', '')
        title = m.get('title') or m.get('module_title', '')
        level = m.get('level', 4)
        credits = m.get('credits') or m.get('detected_credits', 20)
        mean = m.get('mean', 0.0)
        std_dev = m.get('std_dev') if m.get('std_dev') is not None else m.get('std_dev', 0.0)
        
        n_val = m.get('n') if m.get('n') is not None else m.get('cohort_size', 0)
        
        grade_dist = m.get('grade_dist', {})
        pct_1st = grade_dist.get('pct_1st') if grade_dist.get('pct_1st') is not None else m.get('pct_1st', 0.0)
        pct_fail = grade_dist.get('pct_fail') if grade_dist.get('pct_fail') is not None else m.get('pct_fail', 0.0)
        pct_21_above = grade_dist.get('pct_21_above') if grade_dist.get('pct_21_above') is not None else m.get('pct_21_above', 0.0)
        
        normalized_modules.append({
            'code': code,
            'title': title,
            'level': level,
            'credits': credits,
            'mean': mean,
            'std_dev': std_dev,
            'pct_1st': pct_1st,
            'pct_fail': pct_fail,
            'pct_21_above': pct_21_above,
            'n': n_val
        })
    return {
        'programme': snap.get('programme', '') or snap.get('programme_name', ''),
        'year': snap.get('year', '') or snap.get('academic_year', ''),
        'modules': normalized_modules
    }





def analytics_dashboard(request):
    """Calculates final dashboard metrics, flags outliers, and displays comparison charts."""
    confirmed_data = request.session.get('analytics_confirmed_data')
    if not confirmed_data:
        return redirect("analytics_upload")

    # Filter out 0% total component weight modules (pass/fail modules) from statistics.
    # We only exclude if components are defined and their weights sum to 0.
    modules_list = [
        m for m in confirmed_data['modules']
        if not (len(m.get('components', [])) > 0 and sum(c.get('weight', 0) for c in m.get('components', [])) == 0)
    ]
    
    # Process outliers and histogram SVG for each module
    has_outliers = False
    for m in modules_list:
        # Recalculate metrics dynamically to ensure correct fields are populated under all session schemas
        stats = calculate_module_analytics(m.get('scores', []), m.get('level', 4))
        m['mean'] = stats['mean']
        m['median'] = stats['median']
        m['std_dev'] = stats['std_dev']
        m['max'] = stats['max']
        m['min'] = stats['min']
        m['pct_1st'] = stats['pct_1st']
        m['pct_21_above'] = stats['pct_21_above']
        m['pct_fail'] = stats['pct_fail']
        m['cohort_size'] = stats['cohort_size']

        m['flag_high_perf'] = m['pct_1st'] > 20.0
        m['flag_low_perf'] = m['pct_fail'] > 20.0
        m['fail_threshold'] = 50 if m['level'] >= 7 else 40
        if m['flag_high_perf'] or m['flag_low_perf']:
            has_outliers = True
        
        deg_level = 'MEng/MSc' if m['level'] >= 7 else 'BEng'
        # No server-side SVG generation needed; stats contains score_bins for client-side Chart.js

        # Process component statistics and SVGs
        components_stats = []
        comp_names_map = m.get('comp_names_map', {})
        for comp in m.get('components', []):
            if comp.get("weight", 0) == 0:
                continue
            comp_scores = comp.get('scores', [])
            if comp_scores:
                comp_stats = calculate_module_analytics(comp_scores, m['level'])
                # No server-side SVG generation needed; comp_stats contains score_bins for client-side Chart.js
                
                # Format component header using the helper from cohort_report views
                from cohort_report.views import format_component_header
                header_formatted = format_component_header(comp['column'], comp_names_map)
                
                label_short = comp['column'].split(" - ")[0] if " - " in comp['column'] else comp['column']
                
                components_stats.append({
                    "column": comp['column'],
                    "label_short": label_short,
                    "header_formatted": header_formatted,
                    "stats": comp_stats,
                    "weight": comp["weight"],
                    "category": comp.get("category", "Individual CW")
                })
        m['components_stats'] = components_stats

        # Calculate heatmap cells for this module
        m['heatmap_cells'] = []
        for cat in COMPONENT_CATEGORIES:
            comp_means = []
            for comp in m.get('components', []):
                if comp.get('category') == cat and comp.get("weight", 0) > 0:
                    comp_scores = comp.get('scores', [])
                    if comp_scores:
                        comp_means.append(sum(comp_scores) / len(comp_scores))
            mean_val = sum(comp_means) / len(comp_means) if comp_means else None
            m['heatmap_cells'].append({
                'category': cat,
                'val': mean_val
            })

    # Group and aggregate stats by academic level (3, 4, 5, 6, 7)
    level_aggregates = []
    for lvl in [3, 4, 5, 6, 7]:
        modules_at_level = [m for m in modules_list if m.get('level') == lvl]
        lvl_modules_count = len(modules_at_level)
        
        lvl_student_marks = []
        lvl_student_ids = []
        for m in modules_at_level:
            lvl_student_marks.extend(m.get('scores', []))
            lvl_student_ids.extend(m.get('student_ids', [None] * len(m.get('scores', []))))
                
        if lvl_student_marks:
            stats = calculate_module_analytics(lvl_student_marks, lvl)
            
            n_students = len(lvl_student_marks)
            is_pg = (lvl >= 7)
            fail_threshold = 50 if is_pg else 40
            
            p_fail = (sum(1 for x in lvl_student_marks if x < fail_threshold) / n_students) * 100.0
            p_3rd = (sum(1 for x in lvl_student_marks if 40 <= x < 50) / n_students) * 100.0 if not is_pg else 0.0
            p_22 = (sum(1 for x in lvl_student_marks if 50 <= x < 60) / n_students) * 100.0
            p_21 = (sum(1 for x in lvl_student_marks if 60 <= x < 70) / n_students) * 100.0
            p_1st = (sum(1 for x in lvl_student_marks if x >= 70) / n_students) * 100.0
            
            # Count unique student IDs to find actual cohort size, treating None as unique
            seen_ids = set()
            cohort_size = 0
            for s_id in lvl_student_ids:
                if s_id is not None:
                    s_id_str = str(s_id).strip()
                    if s_id_str:
                        if s_id_str not in seen_ids:
                            seen_ids.add(s_id_str)
                            cohort_size += 1
                    else:
                        cohort_size += 1
                else:
                    cohort_size += 1

            level_aggregates.append({
                'level': lvl,
                'modules_count': lvl_modules_count,
                'cohort_size': cohort_size,
                'mean': stats['mean'],
                'median': stats['median'],
                'std_dev': stats['std_dev'],
                'pct_1st': p_1st,
                'pct_21': p_21,
                'pct_22': p_22,
                'pct_3rd': p_3rd,
                'pct_fail': p_fail,
                'pct_21_above': stats['pct_21_above']
            })

    # Historical Trends Processing
    historical_snapshots = request.session.get('analytics_historical_snapshots', [])
    trends_error = request.session.pop('trends_error', None)
    
    trends_data = None
    if historical_snapshots:
        # Create virtual snapshot for current cohort
        current_modules = []
        for m in modules_list:
            stats = calculate_module_analytics(m.get('scores', []), m.get('level', 4))
            current_modules.append({
                'code': m['module_code'],
                'title': m.get('module_title', ''),
                'level': m.get('level', 4),
                'credits': m.get('credits', 20),
                'mean': stats['mean'],
                'std_dev': stats['std_dev'],
                'pct_1st': stats['pct_1st'],
                'pct_fail': stats['pct_fail'],
                'pct_21_above': stats['pct_21_above'],
                'n': stats['cohort_size']
            })
        
        current_snap = {
            'programme': confirmed_data['programme_name'],
            'year': confirmed_data['academic_year'],
            'modules': current_modules
        }
        
        all_snapshots = []
        all_snapshots.append(normalize_snapshot(current_snap))
        for snap in historical_snapshots:
            all_snapshots.append(normalize_snapshot(snap))
            
        snap_by_year = {}
        for snap in all_snapshots:
            snap_by_year[snap['year']] = snap
        
        sorted_years = sorted(list(snap_by_year.keys()))
        sorted_snapshots = [snap_by_year[yr] for yr in sorted_years]
        
        # 1. Programme-level summary metrics across years
        years_list = []
        overall_mean_list = []
        overall_std_dev_list = []
        overall_pct_1st_list = []
        overall_pct_21_list = []
        overall_pct_fail_list = []
        
        for snap in sorted_snapshots:
            yr = snap['year']
            snap_modules = snap['modules']
            
            total_n = sum(m['n'] for m in snap_modules)
            if total_n > 0:
                weighted_mean = sum(m['mean'] * m['n'] for m in snap_modules) / total_n
                weighted_1st = sum(m['pct_1st'] * m['n'] for m in snap_modules) / total_n
                weighted_21 = sum(m['pct_21_above'] * m['n'] for m in snap_modules) / total_n
                weighted_fail = sum(m['pct_fail'] * m['n'] for m in snap_modules) / total_n
                
                pooled_variance = sum(m['n'] * ((m['std_dev'] ** 2) + ((m['mean'] - weighted_mean) ** 2)) for m in snap_modules) / total_n
                weighted_std_dev = math.sqrt(pooled_variance)
            else:
                weighted_mean = 0.0
                weighted_1st = 0.0
                weighted_21 = 0.0
                weighted_fail = 0.0
                weighted_std_dev = 0.0
                
            years_list.append(yr)
            overall_mean_list.append(weighted_mean)
            overall_std_dev_list.append(weighted_std_dev)
            overall_pct_1st_list.append(weighted_1st)
            overall_pct_21_list.append(weighted_21)
            overall_pct_fail_list.append(weighted_fail)
            
        # 2. Module trend table metrics
        all_module_codes = set()
        for snap in sorted_snapshots:
            for m in snap['modules']:
                if m['code']:
                    all_module_codes.add(m['code'])
                    
        module_trends = []
        for code in sorted(list(all_module_codes)):
            history = {}
            latest_title = ""
            latest_level = 4
            
            for snap in sorted_snapshots:
                yr = snap['year']
                for m in snap['modules']:
                    if m['code'] == code:
                        history[yr] = {
                            'mean': m['mean'],
                            'std_dev': m['std_dev'],
                            'pct_1st': m['pct_1st'],
                            'pct_21_above': m['pct_21_above'],
                            'pct_fail': m['pct_fail'],
                            'n': m['n']
                        }
                        latest_title = m['title'] or latest_title
                        latest_level = m.get('level', latest_level)
            
            mean_vals = [history[yr]['mean'] if yr in history else None for yr in sorted_years]
            sparkline_svg = generate_sparkline_svg(mean_vals)
            
            year_columns = []
            for yr in sorted_years:
                if yr in history:
                    year_columns.append({
                        'year': yr,
                        'mean': history[yr]['mean'],
                        'pct_1st': history[yr]['pct_1st'],
                        'pct_fail': history[yr]['pct_fail'],
                        'n': history[yr]['n'],
                        'present': True
                    })
                else:
                    year_columns.append({
                        'year': yr,
                        'present': False
                    })
                    
            module_trends.append({
                'code': code,
                'title': latest_title,
                'level': latest_level,
                'year_columns': year_columns,
                'sparkline_svg': sparkline_svg,
                'history': history,
                'has_history': len(history) >= 2
            })
            
        trends_data = {
            'years': sorted_years,
            'overall_means': overall_mean_list,
            'overall_std_devs': overall_std_dev_list,
            'overall_pct_1st': overall_pct_1st_list,
            'overall_pct_21': overall_pct_21_list,
            'overall_pct_fail': overall_pct_fail_list,
            'module_trends': module_trends,
            'raw_snapshots_count': len(historical_snapshots),
            'colspan': len(sorted_years) * 3 + 3
        }

    return render(request, "programme_analytics/dashboard.html", {
        "programme_name": confirmed_data['programme_name'],
        "academic_year": confirmed_data['academic_year'],
        "modules": modules_list,
        "level_aggregates": level_aggregates,
        "component_categories": COMPONENT_CATEGORIES,
        "has_outliers": has_outliers,
        "trends_data": trends_data,
        "trends_error": trends_error
    })


def download_snapshot(request):
    """Downloads a stateless, anonymised cohort snapshot as a JSON file."""
    confirmed_data = request.session.get('analytics_confirmed_data')
    if not confirmed_data:
        return redirect("analytics_upload")
        
    # Filter out 0% total component weight modules (pass/fail modules) from snapshot.
    # We only exclude if components are defined and their weights sum to 0.
    modules_list = [
        m for m in confirmed_data['modules']
        if not (len(m.get('components', [])) > 0 and sum(c.get('weight', 0) for c in m.get('components', [])) == 0)
    ]
    
    snapshot = {
        'programme': confirmed_data['programme_name'],
        'year': confirmed_data['academic_year'],
        'modules': []
    }
    
    for m in modules_list:
        # Recalculate metrics dynamically to guarantee the correct keys are output regardless of session state
        stats = calculate_module_analytics(m.get('scores', []), m.get('level', 4))
        snapshot['modules'].append({
            'code': m['module_code'],
            'title': m.get('module_title', ''),
            'level': m.get('level', 4),
            'credits': m.get('credits', 20),
            'mean': round(stats['mean'], 2),
            'std_dev': round(stats['std_dev'], 2),
            'grade_dist': {
                'pct_1st': round(stats['pct_1st'], 2),
                'pct_21_above': round(stats['pct_21_above'], 2),
                'pct_fail': round(stats['pct_fail'], 2),
            },
            'score_bins': stats['score_bins'],
            'n': stats['cohort_size']
        })
    
    response = HttpResponse(json.dumps(snapshot, indent=4), content_type="application/json")
    filename = f"snapshot_{confirmed_data['programme_name'].replace(' ', '_')}_{confirmed_data['academic_year'].replace('/', '-')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def upload_snapshots(request):
    """Handles uploading of one or more historical snapshot JSON files."""
    if request.method == "POST":
        uploaded_files = request.FILES.getlist("snapshots")
        if not uploaded_files:
            request.session['trends_error'] = "No snapshot files were selected."
            return redirect(f"{reverse('analytics_dashboard')}#trends")
            
        snapshots = request.session.get('analytics_historical_snapshots', [])
        
        errors = []
        for f in uploaded_files:
            try:
                data = json.load(f)
            except Exception as e:
                errors.append(f"'{f.name}' is not a valid JSON file: {str(e)}")
                continue
                
            if not isinstance(data, dict):
                errors.append(f"'{f.name}' must be a JSON object.")
                continue
                
            programme = data.get('programme') or data.get('programme_name')
            year = data.get('year') or data.get('academic_year')
            modules = data.get('modules')
            
            if not programme or not year or modules is None:
                errors.append(f"'{f.name}' is missing required snapshot fields ('programme', 'year', 'modules').")
                continue
                
            if not isinstance(modules, list):
                errors.append(f"'{f.name}' modules field must be a list.")
                continue
                
            try:
                norm_snap = normalize_snapshot(data)
                # Avoid inserting duplicate years if already exists in list
                snapshots = [s for s in snapshots if s.get('year') != norm_snap['year']]
                snapshots.append(norm_snap)
            except Exception as e:
                errors.append(f"Failed to normalize snapshot '{f.name}': {str(e)}")
                
        if errors:
            request.session['trends_error'] = " ".join(errors)
        else:
            if 'trends_error' in request.session:
                del request.session['trends_error']
                
        request.session['analytics_historical_snapshots'] = snapshots
        request.session.modified = True
        
    return redirect(f"{reverse('analytics_dashboard')}#trends")


def clear_snapshots(request):
    """Clears all historical snapshots from the session."""
    if 'analytics_historical_snapshots' in request.session:
        del request.session['analytics_historical_snapshots']
    if 'trends_error' in request.session:
        del request.session['trends_error']
    request.session.modified = True
    return redirect(f"{reverse('analytics_dashboard')}#trends")
