import re

def module_numeric_mark(value):
    try:
        return float(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0

def component_percentage(student_row, component):
    mark_val = module_numeric_mark(student_row.get(component["column"], 0))
    max_marks = component["max_marks"]
    return (mark_val / max_marks) * 100 if max_marks > 0 else 0

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

def build_module_cohort_weighted_finals(uploaded_data, components):
    cohort_weighted_finals = []

    for row in uploaded_data:
        row_weighted_pct = 0
        for comp in components:
            pct = component_percentage(row, comp)
            row_weighted_pct += (pct * comp["weight"]) / 100
        cohort_weighted_finals.append(round_mark_pct(row_weighted_pct))

    return cohort_weighted_finals
