"""Utility functions for grade band calculations."""
from math import floor


def _round_marks(value):
    """Traditional rounding (always round 0.5 up) for grade marks."""
    return int(floor(value + 0.5))


def _get_grade_band_for_percentage(percentage):
    """
    Return the grade band name for a given percentage.
    
    UK Grade thresholds:
    - 1st: 70-100%
    - 2:1: 60-69%
    - 2:2: 50-59%
    - 3rd: 40-49%
    - Fail: 0-39%
    """
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


def grade_for_percentage(percentage):
    """Public helper that returns the UK grade band for a percentage.

    Wrapper around the internal `_get_grade_band_for_percentage` for use in views.
    """
    return _get_grade_band_for_percentage(percentage)


def _calculate_mark_for_grade(max_marks, target_percentage, expected_grade):
    """
    Calculate a mark value that actually falls within the expected grade band.
    
    Finds the closest integer mark to the target percentage that falls within
    the expected grade band. Checks the rounded value first, then searches
    nearby marks if needed.
    
    Args:
        max_marks: Maximum marks for the category
        target_percentage: Target percentage (e.g., 0.85 for 85%)
        expected_grade: The grade this mark should represent (e.g., "1st")
    
    Returns:
        int: A mark value that falls within the expected grade band
    """
    # Start with the rounded target
    target_mark = _round_marks(max_marks * target_percentage)
    
    # Check if the rounded target is already in the correct grade band
    actual_percentage = (target_mark / max_marks) * 100
    actual_grade = _get_grade_band_for_percentage(actual_percentage)
    
    if actual_grade == expected_grade:
        return target_mark
    
    # Search for the closest valid mark by checking nearby marks
    # Try marks in order of distance from target: target±1, target±2, etc.
    for distance in range(1, max_marks + 1):
        # Try mark above target first (closer to original percentage)
        mark_above = target_mark + distance
        if mark_above <= max_marks:
            percentage_above = (mark_above / max_marks) * 100
            grade_above = _get_grade_band_for_percentage(percentage_above)
            if grade_above == expected_grade:
                return mark_above
        
        # Then try mark below target
        mark_below = target_mark - distance
        if mark_below >= 0:
            percentage_below = (mark_below / max_marks) * 100
            grade_below = _get_grade_band_for_percentage(percentage_below)
            if grade_below == expected_grade:
                return mark_below
    
    # Fallback (shouldn't happen in practice)
    return 0

def validate_subdivision(max_marks, subdivision):
    """
    Check if a subdivision produces valid grade bands without cross-band violations.
    
    Allows duplicate marks within the same grade (e.g., High 2:1 = Low 2:1 = 6)
    but prevents cross-band violations (e.g., Low 1st = 7, High 2:1 = 7).
    
    Args:
        max_marks: Maximum marks for the category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        bool: True if subdivision has no cross-band violations
    """
    bands = calculate_grade_bands(max_marks, subdivision)
    
    # Extract the base grade name (e.g., "1st" from "High 1st" or "Low 1st")
    def get_base_grade(grade_name):
        for base in ["1st", "2:1", "2:2", "3rd", "Fail"]:
            if base in grade_name:
                return base
        return grade_name
    
    # Check for cross-band violations
    for i in range(1, len(bands)):
        current_grade = get_base_grade(bands[i]["grade"])
        previous_grade = get_base_grade(bands[i-1]["grade"])
        
        # If we've moved to a different grade band, marks must be strictly less
        if current_grade != previous_grade:
            if bands[i]["marks"] >= bands[i-1]["marks"]:
                return False
        # Within the same grade band, marks can be equal or less (allow duplicates)
    
    return True


def calculate_grade_bands(max_marks, subdivision, degree_level=None):
    """
    Calculate grade band mark values based on UK grading percentages.
    
    UK UGT Grade thresholds:
    - 1st: 70-100%
    - 2:1: 60-69%
    - 2:2: 50-59%
    - 3rd: 40-49%
    - Fail: 0-39%

    UK Level 7 Grade thresholds:
    - 1st/Dist: 70-100%
    - 2:1/Merit: 60-69%
    - 2:2/Pass: 50-59%
    - Fail: 0-49%
    
    Returns a single representative mark value for each grade band.
    
    Args:
        max_marks: Maximum marks for this category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        List of dicts with grade and marks (single integer value)
    """
    """Calculate grade band mark values based on UK grading percentages.

    Accepts an optional `degree_level` parameter (e.g., 'MEng' or 'MSc' or
    'MEng/MSc') to produce postgraduate-style labels (Dist/Merit/Pass/Fail)
    where appropriate. The internal calculations still use the undergraduate
    grade bands but the returned `grade` labels will be remapped for level 7.
    """
    # Backwards-compatible signature handling: if caller passed a third
    # positional argument for degree_level (TDD tests may call
    # calculate_grade_bands(max_marks, subdivision, degree_level='MEng'))
    # Python will already have that as the third argument; we support an
    # explicit parameter below by checking locals. To keep compatibility we
    # accept an optional keyword-only parameter in the function signature
    # by reading from the calling frame isn't necessary; instead we'll
    # support being called with three args by allowing callers to pass
    # degree_level as a third positional argument in the updated signature.
    
    # NOTE: keep a simple API by supporting degree_level via attribute on
    # the function if necessary; however, easiest is to accept degree_level
    # as optional kwarg. We'll implement by inspecting function arguments
    # as passed by callers in newer code paths. (See below where we add
    # an explicit parameter in the signature.)
    
    # The implementation below checks for a module-level override, but
    # we'll simply implement degree-level mapping after computing bands.
    
    # For backward compatibility we still accept the original 2-arg call.
    
    # Build the undergraduate bands first (original implementation)
    ug_bands = []
    if subdivision == "none":
        ug_bands = [
            {"grade": "Max 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
            {"grade": "High 1st", "marks": _calculate_mark_for_grade(max_marks, 0.90, "1st")},
            {"grade": "Mid 1st", "marks": _calculate_mark_for_grade(max_marks, 0.80, "1st")},
            {"grade": "Low 1st", "marks": _calculate_mark_for_grade(max_marks, 0.70, "1st")},
            {"grade": "2:1", "marks": _calculate_mark_for_grade(max_marks, 0.6, "2:1")},
            {"grade": "2:2", "marks": _calculate_mark_for_grade(max_marks, 0.5, "2:2")},
            {"grade": "3rd", "marks": _calculate_mark_for_grade(max_marks, 0.4, "3rd")},
        ]

    elif subdivision == "high_low":
        ug_bands = [
            {"grade": "Max 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
            {"grade": "High 1st", "marks": _calculate_mark_for_grade(max_marks, 0.85, "1st")},
            {"grade": "Low 1st", "marks": _calculate_mark_for_grade(max_marks, 0.72, "1st")},
            {"grade": "High 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.65, "2:1")},
            {"grade": "Low 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.62, "2:1")},
            {"grade": "High 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.55, "2:2")},
            {"grade": "Low 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.52, "2:2")},
            {"grade": "High 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.45, "3rd")},
            {"grade": "Low 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.42, "3rd")},
        ]

    elif subdivision == "high_mid_low":
        ug_bands = [
            {"grade": "Max 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
            {"grade": "High 1st", "marks": _calculate_mark_for_grade(max_marks, 0.90, "1st")},
            {"grade": "Mid 1st", "marks": _calculate_mark_for_grade(max_marks, 0.80, "1st")},
            {"grade": "Low 1st", "marks": _calculate_mark_for_grade(max_marks, 0.70, "1st")},
            {"grade": "High 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.67, "2:1")},
            {"grade": "Mid 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.63, "2:1")},
            {"grade": "Low 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.60, "2:1")},
            {"grade": "High 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.57, "2:2")},
            {"grade": "Mid 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.53, "2:2")},
            {"grade": "Low 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.50, "2:2")},
            {"grade": "High 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.47, "3rd")},
            {"grade": "Mid 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.43, "3rd")},
            {"grade": "Low 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.40, "3rd")},
        ]

    # Decide if this is M-level (postgraduate) to adjust passing-band labels.
    is_m_level = bool(degree_level and isinstance(degree_level, str) and degree_level.strip().lower().startswith('m'))

    # Helper to build fail sub-bands once based on degree level.
    def _build_fail_sequence(max_marks, ug_bands_list, is_m_level_flag):
        seq = []

        if is_m_level_flag:
            # Use even-split targets (37.5%, 25%, 12.5%, 0%) for M-level fail bands
            close_fail_mark = _round_marks(max_marks * 0.375)
            fail_mark = _round_marks(max_marks * 0.25)
            poor_fail_mark = _round_marks(max_marks * 0.125)
            zero_mark = 0

            seq.append({'grade': 'Close Fail', 'marks': close_fail_mark})
            seq.append({'grade': 'Fail', 'marks': fail_mark})
            seq.append({'grade': 'Poor Fail', 'marks': poor_fail_mark})
            seq.append({'grade': 'Zero Fail', 'marks': zero_mark})

        else:
            # Undergraduate fail anchors: 30%, 20%, 10%, 0%
            seq.append({'grade': 'Close Fail', 'marks': _calculate_mark_for_grade(max_marks, 0.30, 'Fail')})
            seq.append({'grade': 'Fail', 'marks': _calculate_mark_for_grade(max_marks, 0.20, 'Fail')})
            seq.append({'grade': 'Poor Fail', 'marks': _calculate_mark_for_grade(max_marks, 0.10, 'Fail')})
            seq.append({'grade': 'Zero Fail', 'marks': 0})

        return seq

    # Build final bands by appending fail sequence once according to degree level
    if is_m_level:
        mapped = []
        for b in ug_bands:
            name = b['grade']
            marks = b['marks']
            if '1st' in name:
                mapped.append({'grade': name.replace('1st', '1st/Dist'), 'marks': marks})
            elif '2:1' in name:
                mapped.append({'grade': name.replace('2:1', '2:1/Merit'), 'marks': marks})
            elif '2:2' in name:
                mapped.append({'grade': name.replace('2:2', '2:2/Pass'), 'marks': marks})
            else:
                # preserve other bands (e.g., 3rd variants) to maintain ordering
                mapped.append({'grade': name, 'marks': marks})

        # Append M-level fail bands built from UG anchors
        mapped.extend(_build_fail_sequence(max_marks, ug_bands, True))
        return mapped

    # Undergraduate: use UG bands and append UG fail bands once
    final = list(ug_bands)
    final.extend(_build_fail_sequence(max_marks, ug_bands, False))
    return final
