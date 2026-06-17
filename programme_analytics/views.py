import io
import re
import math
import zipfile
import json
import hashlib
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings

from core.mcrf_parser import parse_mcrf_workbook
from core.utils.marks import build_module_cohort_weighted_finals, component_percentage, round_mark_pct
from core.utils.charts import generate_cohort_histogram, inject_svg_tooltips

import matplotlib
# Use non-interactive Agg backend to avoid GUI threads/issues
matplotlib.use('Agg')
matplotlib.rcParams['svg.fonttype'] = 'none'
import matplotlib.pyplot as plt
import numpy as np


def clean_svg(svg_str):
    """Strips XML prolog to make Matplotlib's output safe for inline SVG nesting."""
    if not svg_str:
        return ""
    match = re.search(r'<svg.*', svg_str, re.DOTALL)
    if match:
        return match.group(0)
    return svg_str


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


def generate_programme_comparison_chart(modules_data):
    """Generates an SVG bar chart comparing the mean marks of multiple modules."""
    if not modules_data:
        return ""
    
    codes = [m["module_code"] for m in modules_data]
    means = [m["mean"] for m in modules_data]
    
    # Calculate chart width dynamically (0.6 inches per module code, minimum 12.0)
    chart_width = max(12.0, 0.6 * len(codes))
    fig, ax = plt.subplots(figsize=(chart_width, 4.0))
    
    level_colors = {
        3: '#cbd5e1',
        4: '#10b981',
        5: '#3b82f6',
        6: '#8b5cf6',
        7: '#f59e0b',
    }
    colors_list = [level_colors.get(m.get("level", 4), '#3b82f6') for m in modules_data]
    
    x = np.arange(len(codes))
    bars = ax.bar(x, means, width=0.4, color=colors_list, alpha=0.9, edgecolor='none', zorder=3)
    
    # Add level legend
    import matplotlib.patches as mpatches
    present_levels = sorted(list(set(m.get("level", 4) for m in modules_data)))
    level_labels = {
        3: 'Level 3',
        4: 'Level 4',
        5: 'Level 5',
        6: 'Level 6',
        7: 'Level 7',
    }
    legend_handles = []
    for lvl in present_levels:
        color = level_colors.get(lvl, '#3b82f6')
        label = level_labels.get(lvl, f'Level {lvl}')
        legend_handles.append(mpatches.Patch(color=color, label=label))
    
    if legend_handles:
        ax.legend(handles=legend_handles, loc='upper right', frameon=True, facecolor='white', edgecolor='#e2e8f0', fontsize=9.0)
    
    # Set tooltips for each bar
    for bar, code, mean_val in zip(bars, codes, means):
        bar.set_url(f"tooltip:{code}: {mean_val:.1f}% mean")
    
    ax.set_ylabel('Mean Score (%)', color='#475569', size=11, fontfamily='DejaVu Sans')
    ax.set_xticks(x)
    ax.set_xticklabels(codes, color='#475569', size=10, fontfamily='DejaVu Sans', rotation=15, ha='right')
    ax.set_ylim(0, 100)
    
    ax.grid(True, axis='y', color='#e2e8f0', linestyle=':', linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    
    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('#cbd5e1')
    
    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=10)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)
    
    from core.utils.charts import inject_svg_tooltips
    return clean_svg(inject_svg_tooltips(buf.getvalue().decode('utf-8')))


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
                            if name.endswith(('.xls', '.xlsx')) and not name.startswith('__MACOSX/') and not name.split('/')[-1].startswith('.'):
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
                                            'module_info': module_info
                                        })
                                except Exception as e:
                                    errors.append(f"Failed to parse '{name}' inside zip: {str(e)}")
                except Exception as e:
                    errors.append(f"Failed to extract zip file '{filename}': {str(e)}")
            elif filename.endswith(('.xls', '.xlsx')):
                try:
                    headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(uploaded_file)
                    parsed_modules.append({
                        'filename': filename,
                        'headers': headers,
                        'data_rows': data_rows,
                        'module_info': module_info
                    })
                except Exception as e:
                    errors.append(f"Failed to parse '{filename}': {str(e)}")
            else:
                errors.append(f"Unsupported file format for '{filename}'. Only .xls, .xlsx, and .zip files are supported.")

        if errors:
            return render(request, "programme_analytics/upload.html", {
                "error": " ".join(errors)
            })

        if not parsed_modules:
            return render(request, "programme_analytics/upload.html", {
                "error": "No valid MCRF spreadsheets were found in the uploaded files."
            })

        modules_data = []
        for pm in parsed_modules:
            headers = pm['headers']
            data_rows = pm['data_rows']
            module_info = pm['module_info']
            
            components = []
            for h in headers:
                hl = h.lower()
                if any(kw in hl for kw in ["name", "student", "id", "number", "username"]):
                    continue
                if any(kw in hl for kw in ["total", "overall", "average", "final", "module"]):
                    continue
                if "mark" in hl:
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

            student_scores = {}
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
                
                # Extract raw student IDs, normalize, hash and map to final scores
                salt = getattr(settings, "ANALYTICS_SALT", "default_programme_analytics_salt_for_gdpr_compliance")
                for row in data_rows:
                    student_id = extract_student_id(row)
                    if student_id:
                        row_weighted_pct = 0
                        for comp in components:
                            pct = component_percentage(row, comp)
                            row_weighted_pct += (pct * comp["weight"]) / 100
                        final_score = round_mark_pct(row_weighted_pct)
                        norm_id = student_id.strip().lower()
                        hashed_id = hashlib.sha256((salt + norm_id).encode()).hexdigest()
                        student_scores[hashed_id] = final_score
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
                'detected_level': detected_level,
                'detected_credits': module_info.get("detected_credits", 20),
                'student_scores': student_scores,
                'scores': scores,
                'year': module_info.get("year", ""),
                'period': module_info.get("period", ""),
                'occurrence': module_info.get("occurrence", ""),
                'components': components_data,
                'comp_names_map': module_info.get("comp_names_map", {}),
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

                scores = m.get('scores', [])
                stats = calculate_module_analytics(scores, level)

                # Process components and their selected normalized categories
                processed_components = []
                for comp_idx, comp in enumerate(m.get('components', [])):
                    cat = request.POST.get(f"comp_cat_{idx}_{comp_idx}", comp.get("detected_category", "Individual CW")).strip()
                    if cat not in COMPONENT_CATEGORIES:
                        cat = "Individual CW"
                    processed_components.append({
                        "column": comp["column"],
                        "weight": comp["weight"],
                        "scores": comp.get("scores", []),
                        "category": cat
                    })

                confirmed_modules.append({
                    'filename': m['filename'],
                    'module_code': code,
                    'module_title': title,
                    'level': level,
                    'credits': credits,
                    'detected_credits': credits,
                    'student_scores': m.get('student_scores', {}),
                    'scores': scores,
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

            if not error:
                # Sort confirmed modules by module code in case the user edited the codes
                confirmed_modules.sort(key=lambda x: x['module_code'])
                request.session['analytics_confirmed_data'] = {
                    'programme_name': programme_name,
                    'academic_year': academic_year,
                    'modules': confirmed_modules
                }
                request.session.modified = True
                return redirect("analytics_dashboard")

    return render(request, "programme_analytics/confirm.html", {
        "modules": uploaded_modules,
        "default_year": default_year,
        "error": error
    })


def generate_normalised_overlay_chart(modules_list):
    """
    Generates an SVG line chart overlaying module grade distributions.
    Normalises cohort count to percentages.
    """
    if not modules_list:
        return ""

    bin_labels = ['AB', '0-9%', '10-19%', '20-29%', '30-39%', '40-49%', '50-59%', '60-69%', '70-79%', '80-89%', '90-100%']
    x = np.arange(len(bin_labels))

    fig, ax = plt.subplots(figsize=(10.0, 5.0))

    colors = ['#4361ee', '#ff006e', '#3a0ca3', '#7209b7', '#4cc9f0', '#ff7a59', '#10b981', '#f59e0b', '#64748b']

    for idx, m in enumerate(modules_list):
        scores = m.get('scores', [])
        if not scores:
            continue
        stats = calculate_module_analytics(scores, m.get('level', 4))
        n = stats['cohort_size']
        if n == 0:
            continue

        sb = stats['score_bins']
        y_vals = []
        y_vals.append((sb['absent'] / n) * 100.0)
        for b_count in sb['bins']:
            y_vals.append((b_count / n) * 100.0)

        color = colors[idx % len(colors)]
        lines = ax.plot(x, y_vals, label=m['module_code'], color=color, linewidth=2.0, marker='o', markersize=6, alpha=0.85, zorder=4)
        for line in lines:
            line.set_url(f"tooltip:{m['module_code']} - {m['module_title']}")

        for xi, yi, bl in zip(x, y_vals, bin_labels):
            point = ax.scatter(xi, yi, color=color, s=35, zorder=5)
            point.set_url(f"tooltip:{m['module_code']} - {bl}: {yi:.1f}% of cohort")

    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels, rotation=15, ha='right', fontsize=9.5)
    ax.set_xlabel('Score Band / Status', color='#475569', size=12, fontweight='semibold')
    ax.set_ylabel('% of Cohort', color='#475569', size=12, fontweight='semibold')
    ax.set_ylim(-2, 105)

    ax.grid(True, axis='y', color='#e2e8f0', linestyle='--', linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color('#cbd5e1')

    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=9.5)
    ax.legend(loc='upper right', fontsize=9.5, frameon=True, facecolor='white', edgecolor='#e2e8f0')

    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)

    svg_str = buf.getvalue().decode('utf-8')
    return inject_svg_tooltips(svg_str)


def generate_level_cohort_chart(level_data):
    """
    Generates an SVG bar chart comparing grade distributions across academic levels.
    """
    if not level_data:
        return ""

    level_data = sorted(level_data, key=lambda x: x['level'])

    levels = [f"Level {item['level']}" for item in level_data]
    pct_fail = [item.get('pct_fail', 0.0) for item in level_data]
    pct_3rd = [item.get('pct_3rd', 0.0) for item in level_data]
    pct_22 = [item.get('pct_22', 0.0) for item in level_data]
    pct_21 = [item.get('pct_21', 0.0) for item in level_data]
    pct_1st = [item.get('pct_1st', 0.0) for item in level_data]

    x = np.arange(len(levels))
    width = 0.15

    fig, ax = plt.subplots(figsize=(8.0, 4.5))

    fail_color = '#ef4444'
    third_color = '#f59e0b'
    two_two_color = '#8b5cf6'
    two_one_color = '#3b82f6'
    first_color = '#10b981'

    rects1 = ax.bar(x - 2 * width, pct_fail, width, label='Fail', color=fail_color, alpha=0.9, zorder=3)
    rects2 = ax.bar(x - width, pct_3rd, width, label='3rd Class', color=third_color, alpha=0.9, zorder=3)
    rects3 = ax.bar(x, pct_22, width, label='2:2 Class', color=two_two_color, alpha=0.9, zorder=3)
    rects4 = ax.bar(x + width, pct_21, width, label='2:1 Class', color=two_one_color, alpha=0.9, zorder=3)
    rects5 = ax.bar(x + 2 * width, pct_1st, width, label='1st Class', color=first_color, alpha=0.9, zorder=3)

    for bar, lvl in zip(rects1, levels):
        bar.set_url(f"tooltip:{lvl} Fail: {bar.get_height():.1f}%")
    for bar, lvl in zip(rects2, levels):
        bar.set_url(f"tooltip:{lvl} 3rd Class: {bar.get_height():.1f}%")
    for bar, lvl in zip(rects3, levels):
        bar.set_url(f"tooltip:{lvl} 2:2 Class: {bar.get_height():.1f}%")
    for bar, lvl in zip(rects4, levels):
        bar.set_url(f"tooltip:{lvl} 2:1 Class: {bar.get_height():.1f}%")
    for bar, lvl in zip(rects5, levels):
        bar.set_url(f"tooltip:{lvl} 1st Class: {bar.get_height():.1f}%")

    ax.set_ylabel('Percentage (%)', color='#475569', size=11, fontweight='semibold')
    ax.set_xticks(x)
    ax.set_xticklabels(levels, fontsize=10, fontweight='semibold')
    ax.set_ylim(0, 105)

    ax.grid(True, axis='y', color='#e2e8f0', linestyle='--', linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color('#cbd5e1')

    ax.tick_params(axis='both', which='both', length=0, colors='#475569', labelsize=10)
    ax.legend(loc='upper right', fontsize=9.5, frameon=True, facecolor='white', edgecolor='#e2e8f0')

    buf = io.BytesIO()
    plt.savefig(buf, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)

    svg_str = buf.getvalue().decode('utf-8')
    return inject_svg_tooltips(svg_str)


def analytics_dashboard(request):
    """Calculates final dashboard metrics, flags outliers, and displays comparison charts."""
    confirmed_data = request.session.get('analytics_confirmed_data')
    if not confirmed_data:
        return redirect("analytics_upload")

    modules_list = confirmed_data['modules']
    
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
        histogram_svg = generate_cohort_histogram(m['scores'], student_score=None, degree_level=deg_level)
        m['chart_svg'] = clean_svg(histogram_svg)

        # Process component statistics and SVGs
        components_stats = []
        comp_names_map = m.get('comp_names_map', {})
        for comp in m.get('components', []):
            comp_scores = comp.get('scores', [])
            if comp_scores:
                comp_stats = calculate_module_analytics(comp_scores, m['level'])
                comp_chart_svg = generate_cohort_histogram(comp_scores, student_score=None, degree_level=deg_level)
                comp_chart_svg_clean = clean_svg(comp_chart_svg)
                
                # Format component header using the helper from cohort_report views
                from cohort_report.views import format_component_header
                header_formatted = format_component_header(comp['column'], comp_names_map)
                
                label_short = comp['column'].split(" - ")[0] if " - " in comp['column'] else comp['column']
                
                components_stats.append({
                    "column": comp['column'],
                    "label_short": label_short,
                    "header_formatted": header_formatted,
                    "stats": comp_stats,
                    "chart_svg": comp_chart_svg_clean,
                    "weight": comp["weight"],
                    "category": comp.get("category", "Individual CW")
                })
        m['components_stats'] = components_stats

        # Calculate heatmap cells for this module
        m['heatmap_cells'] = []
        for cat in COMPONENT_CATEGORIES:
            comp_means = []
            for comp in m.get('components', []):
                if comp.get('category') == cat:
                    comp_scores = comp.get('scores', [])
                    if comp_scores:
                        comp_means.append(sum(comp_scores) / len(comp_scores))
            mean_val = sum(comp_means) / len(comp_means) if comp_means else None
            m['heatmap_cells'].append({
                'category': cat,
                'val': mean_val
            })

    # Group and aggregate stats by academic level (4, 5, 6, 7)
    level_aggregates = []
    for lvl in [4, 5, 6, 7]:
        modules_at_level = [m for m in modules_list if m.get('level') == lvl]
        lvl_modules_count = len(modules_at_level)
        
        student_module_marks = {}
        for m in modules_at_level:
            m_credits = m.get('credits', 20)
            m_student_scores = m.get('student_scores', {})
            if not m_student_scores and m.get('scores'):
                m_student_scores = {f"dummy_{m['module_code']}_{i}": score for i, score in enumerate(m['scores'])}
            for stud_hash, mark in m_student_scores.items():
                if stud_hash not in student_module_marks:
                    student_module_marks[stud_hash] = []
                student_module_marks[stud_hash].append((mark, m_credits))
                
        lvl_student_marks = []
        for stud_hash, marks_credits in student_module_marks.items():
            total_weighted_marks = sum(mark * cred for mark, cred in marks_credits)
            total_credits = sum(cred for mark, cred in marks_credits)
            if total_credits > 0:
                lvl_student_marks.append(total_weighted_marks / total_credits)
                
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
            
            level_aggregates.append({
                'level': lvl,
                'modules_count': lvl_modules_count,
                'cohort_size': n_students,
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

    # Generate charts
    means_chart_svg = generate_programme_comparison_chart(modules_list)
    overlay_chart_svg = clean_svg(generate_normalised_overlay_chart(modules_list))
    level_chart_svg = clean_svg(generate_level_cohort_chart(level_aggregates))

    return render(request, "programme_analytics/dashboard.html", {
        "programme_name": confirmed_data['programme_name'],
        "academic_year": confirmed_data['academic_year'],
        "modules": modules_list,
        "means_chart_svg": means_chart_svg,
        "overlay_chart_svg": overlay_chart_svg,
        "level_chart_svg": level_chart_svg,
        "level_aggregates": level_aggregates,
        "component_categories": COMPONENT_CATEGORIES,
        "has_outliers": has_outliers
    })


def download_snapshot(request):
    """Downloads a stateless, anonymised cohort snapshot as a JSON file."""
    confirmed_data = request.session.get('analytics_confirmed_data')
    if not confirmed_data:
        return redirect("analytics_upload")
        
    modules_list = confirmed_data['modules']
    
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
