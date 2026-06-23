import math
import re
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string

from core.mcrf_parser import parse_mcrf_workbook, is_assessment_component_column
from core.utils.charts import generate_cohort_histogram, generate_scatter_plot
from module_summary.views import parse_non_negative_int
from core.utils.marks import (
    module_numeric_mark,
    component_percentage,
    round_mark_pct,
    build_module_cohort_weighted_finals
)

def upload_cohort_data(request):
    """
    Step 1: Upload View
    Accepts a single completed MCRF spreadsheet, parses it in-memory,
    auto-infers columns, and saves data to session.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return render(request, "cohort_report/upload.html", {"error": "Please select a file to upload."})
            
        try:
            headers, data_rows, is_mcrf, module_info = parse_mcrf_workbook(uploaded_file)
            
            inferred_mappings = {
                "components": [],
                "degree_level": "BEng",
                "module_code": module_info.get("module_code", ""),
                "module_title": module_info.get("module_title", ""),
                "comp_names_map": module_info.get("comp_names_map", {}),
                "year": module_info.get("year", ""),
                "period": module_info.get("period", ""),
                "occurrence": module_info.get("occurrence", ""),
            }
            
            # Infer Component Mark Columns
            for h in headers:
                if is_assessment_component_column(h):
                    inferred_mappings["components"].append({
                        "column": h,
                        "max_marks": 100,
                        "weight": 0,
                        "type": "numeric"
                    })
                    
            # Check if explicit weights in header
            has_explicit_weights = False
            for comp in inferred_mappings["components"]:
                weight_match = re.search(r'(\d+)\s*%', comp["column"])
                if weight_match:
                    comp["weight"] = int(weight_match.group(1))
                    has_explicit_weights = True
                    
            # Split weights evenly if not explicit
            if not has_explicit_weights:
                num_comps = len(inferred_mappings["components"])
                if num_comps > 0:
                    even_weight = 100 // num_comps
                    for idx, comp in enumerate(inferred_mappings["components"]):
                        if idx == num_comps - 1:
                            comp["weight"] = 100 - (even_weight * (num_comps - 1))
                        else:
                            comp["weight"] = even_weight

            if not inferred_mappings["components"]:
                return render(request, "cohort_report/upload.html", {
                    "error": "No component mark columns were detected. Please upload an MCRF with columns containing component marks."
                })
                        
            request.session["cohort_headers"] = headers
            request.session["cohort_uploaded_data"] = data_rows
            request.session["cohort_mappings"] = inferred_mappings
            request.session.modified = True
            
            return redirect("cohort_report_confirm")
            
        except Exception as e:
            return render(request, "cohort_report/upload.html", {"error": f"Failed to parse MCRF file: {str(e)}"})
            
    return render(request, "cohort_report/upload.html")

def confirm_cohort_mappings(request):
    """
    Step 2: Alignment View
    Academics verify column selections, set component weights, and choose the degree level (BEng vs MEng/MSc).
    """
    headers = request.session.get("cohort_headers")
    mappings = request.session.get("cohort_mappings")
    uploaded_data = request.session.get("cohort_uploaded_data")
    
    if not headers or not mappings or not uploaded_data:
        return redirect("cohort_report_upload")

    if not mappings.get("components"):
        return render(request, "cohort_report/confirm.html", {
            "headers": headers,
            "mappings": mappings,
            "sample_rows": uploaded_data[:3],
            "error": "No component mark columns were detected.",
        })
        
    error = None
    if request.method == "POST":
        mappings["module_code"] = request.POST.get("module_code", "").strip()
        mappings["module_title"] = request.POST.get("module_title", "").strip()
        mappings["degree_level"] = request.POST.get("degree_level", "BEng")
        mappings["year"] = request.POST.get("year", "").strip()
        mappings["period"] = request.POST.get("period", "").strip()
        mappings["occurrence"] = request.POST.get("occurrence", "").strip()
        
        # Read weights
        updated_comps = []
        total_weight = 0
        
        for idx, comp_dict in enumerate(mappings["components"]):
            col_name = comp_dict["column"]
            weight = parse_non_negative_int(request.POST.get(f"weight_{idx}"))
            if weight is None or weight > 100:
                error = f"Weight for {col_name} must be a whole number between 0 and 100."
                return render(request, "cohort_report/confirm.html", {
                    "headers": headers,
                    "mappings": mappings,
                    "sample_rows": uploaded_data[:3],
                    "error": error,
                })
            
            total_weight += weight
            updated_comps.append({
                "column": col_name,
                "max_marks": 100,
                "weight": weight,
                "type": "numeric"
            })
            
        mappings["components"] = updated_comps
        request.session["cohort_mappings"] = mappings
        request.session.modified = True
        
        # Enforce weight sum validation
        if total_weight != 100:
            error = f"Total component weight must sum to exactly 100% (currently {total_weight}%)."
        else:
            return redirect("cohort_report_results")
            
    return render(request, "cohort_report/confirm.html", {
        "headers": headers,
        "mappings": mappings,
        "sample_rows": uploaded_data[:3],
        "error": error
    })

def compute_stats(scores, degree_level="BEng"):
    """
    Computes statistical aggregate metrics for a list of score percentages.
    """
    if not scores:
        return {
            "mean": 0.0,
            "std_dev": 0.0,
            "max": 0.0,
            "min": 0.0,
            "pct_1st": 0.0,
            "pct_21_above": 0.0,
            "pct_fail": 0.0,
        }
    n = len(scores)
    mean_val = sum(scores) / n
    variance = sum((x - mean_val) ** 2 for x in scores) / n
    std_dev = math.sqrt(variance)
    
    sorted_scores = sorted(scores)
    mid = n // 2
    median_val = sorted_scores[mid] if n % 2 != 0 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2

    pct_1st = (sum(1 for x in scores if x >= 70) / n) * 100
    pct_21_above = (sum(1 for x in scores if x >= 60) / n) * 100
    
    is_m = bool(degree_level and isinstance(degree_level, str) and degree_level.strip().lower().startswith('m'))
    fail_threshold = 50 if is_m else 40
    pct_fail = (sum(1 for x in scores if x < fail_threshold) / n) * 100
    
    return {
        "mean": mean_val,
        "median": median_val,
        "std_dev": std_dev,
        "max": max(scores),
        "min": min(scores),
        "pct_1st": pct_1st,
        "pct_21_above": pct_21_above,
        "pct_fail": pct_fail,
    }

def clean_svg(svg_str):
    """
    Strips XML prolog to make Matplotlib's output safe for inline SVG nesting.
    """
    if not svg_str:
        return ""
    match = re.search(r'<svg.*', svg_str, re.DOTALL)
    if match:
        return match.group(0)
    return svg_str

def normalize_comp_code(code_str):
    if not code_str:
        return ""
    s = str(code_str).strip().split('.')[0]
    if s.isdigit():
        return f"{int(s):03d}"
    return s.upper()

def format_component_header(column_name, comp_names_map=None):
    """
    Parses column name to build formatted header like "001 - Industry compatible written submission".
    """
    if not column_name:
        return ""
        
    # 1. Extract the component code using robust regex
    CODE_EXTRACT_RE = re.compile(r'\b(\d{1,3}|CW\d|EX\d|EXAM\d?)\b', re.IGNORECASE)
    m = CODE_EXTRACT_RE.search(column_name)
    code = m.group(1) if m else ""
    code_norm = normalize_comp_code(code)
    
    # 2. Look up in comp_names_map
    if comp_names_map and code_norm:
        code_upper = code_norm.upper()
        if code_upper in comp_names_map:
            return f"{code_norm} - {comp_names_map[code_upper]}"
            
    # 3. Fallback: split by space-dash-space or other dashes
    parts = [p.strip() for p in re.split(r'\s*[-:–—]\s*', column_name)]
    if len(parts) >= 3:
        name = ""
        for p in parts:
            p_lower = p.lower()
            if p_lower in ["mark", "grade", "result", "score"]:
                continue
            if len(p) <= 6 and any(c.isdigit() for c in p):
                continue
            name = p
        if code_norm and name:
            return f"{code_norm} - {name}"
        elif name:
            return name
            
    # Fallback to standard split
    parts_standard = [p.strip() for p in column_name.split(" - ")]
    if len(parts_standard) == 2:
        return parts_standard[0]
        
    return column_name

def pearson_correlation(x, y):
    """
    Computes the Pearson correlation coefficient between two lists of numbers.
    Returns None if standard deviations are zero or length is less than 3.
    """
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

def get_report_context(request):
    """
    Helper to compute statistics and generate SVG histogram charts.
    Does not expose any per-student details.
    """
    uploaded_data = request.session.get("cohort_uploaded_data")
    mappings = request.session.get("cohort_mappings")
    
    if not uploaded_data or not mappings:
        return None
        
    components = mappings.get("components", [])
    degree_level = mappings.get("degree_level", "BEng")
    comp_names_map = mappings.get("comp_names_map", {})
    
    # Calculate per-component stats & charts
    components_stats = []
    cohort_weighted_finals = build_module_cohort_weighted_finals(uploaded_data, components)
        
    for comp in components:
        if comp.get("weight", 0) == 0:
            continue
        col_name = comp["column"]
        scores = [round_mark_pct(component_percentage(row, comp)) for row in uploaded_data]
        stats = compute_stats(scores, degree_level=degree_level)
        
        # Generate histogram
        chart_svg = generate_cohort_histogram(scores, student_score=None, degree_level=degree_level)
        chart_svg_clean = clean_svg(chart_svg)
        
        label_short = col_name.split(" - ")[0] if " - " in col_name else col_name
        
        components_stats.append({
            "column": col_name,
            "label_short": label_short,
            "header_formatted": format_component_header(col_name, comp_names_map),
            "stats": stats,
            "chart_svg": chart_svg_clean,
            "weight": comp["weight"]
        })
        
    # Calculate within-module component correlations (scatter plots)
    scatter_charts = []
    active_comps = [comp for comp in components if comp.get("weight", 0) > 0]
    
    if len(active_comps) > 1:
        import itertools
        comp_scores = {}
        comp_labels = {}
        for comp in active_comps:
            col_name = comp["column"]
            comp_scores[col_name] = [round_mark_pct(component_percentage(row, comp)) for row in uploaded_data]
            comp_labels[col_name] = col_name.split(" - ")[0] if " - " in col_name else col_name
            
        for comp_i, comp_j in itertools.combinations(active_comps, 2):
            col_i = comp_i["column"]
            col_j = comp_j["column"]
            label_i = comp_labels[col_i]
            label_j = comp_labels[col_j]
            
            raw_x = comp_scores[col_i]
            raw_y = comp_scores[col_j]
            
            # Exclude non-submissions (marks of 0%) in either component
            filtered_xy = [(x, y) for x, y in zip(raw_x, raw_y) if x > 0 and y > 0]
            if filtered_xy:
                filtered_x, filtered_y = zip(*filtered_xy)
                filtered_x = list(filtered_x)
                filtered_y = list(filtered_y)
            else:
                filtered_x, filtered_y = [], []
            
            r = pearson_correlation(filtered_x, filtered_y)
            
            # Generate the scatter plot SVG using raw data (with 0% marks plotted in red)
            chart_svg = generate_scatter_plot(
                raw_x,
                raw_y,
                label_i,
                label_j,
                degree_level=degree_level,
                r=r
            )
            
            scatter_charts.append({
                "comp_x": label_i,
                "comp_y": label_j,
                "r": r,
                "chart_svg": clean_svg(chart_svg)
            })

    # Calculate overall module stats & charts
    overall_stats = compute_stats(cohort_weighted_finals, degree_level=degree_level)
    overall_chart_svg = generate_cohort_histogram(cohort_weighted_finals, student_score=None, degree_level=degree_level)
    overall_chart_svg_clean = clean_svg(overall_chart_svg)
    
    is_m = bool(degree_level and isinstance(degree_level, str) and degree_level.strip().lower().startswith('m'))
    fail_threshold = 50 if is_m else 40

    return {
        "module_code": mappings.get("module_code", "COMP101"),
        "module_title": mappings.get("module_title", "Module Summary"),
        "degree_level": degree_level,
        "year": mappings.get("year", ""),
        "period": mappings.get("period", ""),
        "occurrence": mappings.get("occurrence", ""),
        "overall_stats": overall_stats,
        "overall_chart_svg": overall_chart_svg_clean,
        "components_stats": components_stats,
        "scatter_charts": scatter_charts,
        "fail_threshold": fail_threshold,
        "cohort_size": len(uploaded_data)
    }


def render_cohort_report(request):
    """
    Step 3: Render Report View
    Calculates aggregate statistical performance across the cohort and renders inside the browser.
    """
    context = get_report_context(request)
    if not context:
        return redirect("cohort_report_upload")
        
    context["base_template"] = "base.html"
    context["is_download"] = False
    context["show_download_button"] = True
    return render(request, "cohort_report/report.html", context)

def download_cohort_report(request):
    """
    Step 4: Download Self-Contained Report View
    Calculates stats, compiles them in a single, completely offline-compatible HTML file,
    and returns it as a downloadable file response.
    """
    context = get_report_context(request)
    if not context:
        return redirect("cohort_report_upload")

    # Render the self-contained download template with embedded charts and CSS
    rendered_html = render_to_string("cohort_report/report_download.html", context, request=request)

    filename = f"cohort_report_{context['module_code'].replace(' ', '_')}.html"
    response = HttpResponse(rendered_html, content_type="text/html")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
