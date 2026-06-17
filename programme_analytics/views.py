import io
import re
import math
import zipfile
import json
from django.shortcuts import render, redirect
from django.http import HttpResponse

from core.mcrf_parser import parse_mcrf_workbook
from core.utils.marks import build_module_cohort_weighted_finals, component_percentage, round_mark_pct
from core.utils.charts import generate_cohort_histogram

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
    
    # Calculate chart width dynamically (0.5 inches per module code, minimum 8.0)
    chart_width = max(8.0, 0.5 * len(codes))
    fig, ax = plt.subplots(figsize=(chart_width, 4.0))
    bar_color = '#7bafd4'  # Standard theme blue
    
    x = np.arange(len(codes))
    bars = ax.bar(x, means, width=0.4, color=bar_color, alpha=0.9, edgecolor='none', zorder=3)
    
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

            if components and data_rows:
                scores = build_module_cohort_weighted_finals(data_rows, components)
                # Store component scores
                components_data = []
                for comp in components:
                    col_name = comp["column"]
                    comp_scores = [round_mark_pct(component_percentage(row, comp)) for row in data_rows]
                    components_data.append({
                        "column": col_name,
                        "weight": comp["weight"],
                        "scores": comp_scores
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
                'detected_level': detected_level,
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

                if not code or not title:
                    error = "Module Code and Module Title cannot be empty."
                    break

                scores = m.get('scores', [])
                stats = calculate_module_analytics(scores, level)

                confirmed_modules.append({
                    'filename': m['filename'],
                    'module_code': code,
                    'module_title': title,
                    'level': level,
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
                    'components': m.get('components', []),
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
                    "weight": comp["weight"]
                })
        m['components_stats'] = components_stats

    # Comparison chart of module means
    means_chart_svg = generate_programme_comparison_chart(modules_list)

    return render(request, "programme_analytics/dashboard.html", {
        "programme_name": confirmed_data['programme_name'],
        "academic_year": confirmed_data['academic_year'],
        "modules": modules_list,
        "means_chart_svg": means_chart_svg,
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
            'level': m.get('level', 4),
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
