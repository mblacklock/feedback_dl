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


def _calculate_mark_for_grade(max_marks, target_percentage, expected_grade):
    """
    Calculate a mark value that actually falls within the expected grade band.
    
    Starts with the target percentage, rounds to integer, then validates
    the resulting mark is actually in the expected grade band. If not,
    reduces by 1 until it is.
    
    Args:
        max_marks: Maximum marks for the category
        target_percentage: Target percentage (e.g., 0.85 for 85%)
        expected_grade: The grade this mark should represent (e.g., "1st")
    
    Returns:
        int: A mark value that falls within the expected grade band
    """
    # Start with the rounded target
    mark = _round_marks(max_marks * target_percentage)
    
    # Check if this mark is in the correct grade band
    actual_percentage = (mark / max_marks) * 100
    actual_grade = _get_grade_band_for_percentage(actual_percentage)
    
    # If it's in the wrong band, reduce by 1 until it's correct
    while actual_grade != expected_grade and mark > 0:
        mark -= 1
        actual_percentage = (mark / max_marks) * 100
        actual_grade = _get_grade_band_for_percentage(actual_percentage)
    
    return mark


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


def calculate_grade_bands(max_marks, subdivision):
    """
    Calculate grade band mark values based on UK grading percentages.
    
    UK Grade thresholds:
    - 1st: 70-100%
    - 2:1: 60-69%
    - 2:2: 50-59%
    - 3rd: 40-49%
    - Fail: 0-39%
    
    Returns a single representative mark value for each grade band.
    
    Args:
        max_marks: Maximum marks for this category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        List of dicts with grade and marks (single integer value)
    """
    bands = []
    
    if subdivision == "none":
        # Expanded subdivision - maximizes mark coverage by always expanding 1st and Fail bands
        # Provides more granularity at extremes (excellence and poor performance)
        # while keeping middle grades simple
        bands = [
            {"grade": "Maximum 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
            {"grade": "High 1st", "marks": _calculate_mark_for_grade(max_marks, 0.90, "1st")},
            {"grade": "Mid 1st", "marks": _calculate_mark_for_grade(max_marks, 0.80, "1st")},
            {"grade": "Low 1st", "marks": _calculate_mark_for_grade(max_marks, 0.70, "1st")},
            {"grade": "2:1", "marks": _calculate_mark_for_grade(max_marks, 0.6, "2:1")},
            {"grade": "2:2", "marks": _calculate_mark_for_grade(max_marks, 0.5, "2:2")},
            {"grade": "3rd", "marks": _calculate_mark_for_grade(max_marks, 0.4, "3rd")},
            {"grade": "Close Fail", "marks": _calculate_mark_for_grade(max_marks, 0.30, "Fail")},
            {"grade": "Fail", "marks": _calculate_mark_for_grade(max_marks, 0.20, "Fail")},
            {"grade": "Poor Fail", "marks": _calculate_mark_for_grade(max_marks, 0.10, "Fail")},
            {"grade": "Zero Fail", "marks": _calculate_mark_for_grade(max_marks, 0.00, "Fail")},
        ]
    
    elif subdivision == "high_low":
        # High/Low subdivision - split each grade band, validated to stay in correct band
        # Maximum 1st: target 100%
        # High 1st: target 85%, Low 1st: target 72%
        # High 2:1: target 65%, Low 2:1: target 62%
        # High 2:2: target 55%, Low 2:2: target 52%
        # High 3rd: target 45%, Low 3rd: target 42%
        # Close Fail: target 30%
        # Fail: target 20%
        # Poor Fail: target 10%
        bands = [
            {"grade": "Maximum 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
            {"grade": "High 1st", "marks": _calculate_mark_for_grade(max_marks, 0.85, "1st")},
            {"grade": "Low 1st", "marks": _calculate_mark_for_grade(max_marks, 0.72, "1st")},
            {"grade": "High 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.65, "2:1")},
            {"grade": "Low 2:1", "marks": _calculate_mark_for_grade(max_marks, 0.62, "2:1")},
            {"grade": "High 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.55, "2:2")},
            {"grade": "Low 2:2", "marks": _calculate_mark_for_grade(max_marks, 0.52, "2:2")},
            {"grade": "High 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.45, "3rd")},
            {"grade": "Low 3rd", "marks": _calculate_mark_for_grade(max_marks, 0.42, "3rd")},
            {"grade": "Close Fail", "marks": _calculate_mark_for_grade(max_marks, 0.30, "Fail")},
            {"grade": "Fail", "marks": _calculate_mark_for_grade(max_marks, 0.20, "Fail")},
            {"grade": "Poor Fail", "marks": _calculate_mark_for_grade(max_marks, 0.10, "Fail")},
            {"grade": "Zero Fail", "marks": _calculate_mark_for_grade(max_marks, 0.00, "Fail")},
        ]
    
    elif subdivision == "high_mid_low":
        # High/Mid/Low subdivision - split each grade band in thirds, validated to stay in correct band
        # Maximum 1st: target 100%
        # High 1st: target 90%, Mid 1st: target 80%, Low 1st: target 70%
        # High 2:1: target 67%, Mid 2:1: target 63%, Low 2:1: target 60%
        # High 2:2: target 57%, Mid 2:2: target 53%, Low 2:2: target 50%
        # High 3rd: target 47%, Mid 3rd: target 43%, Low 3rd: target 40%
        # Close Fail: target 30%
        # Fail: target 20%
        # Poor Fail: target 10%
        bands = [
            {"grade": "Maximum 1st", "marks": _calculate_mark_for_grade(max_marks, 1.00, "1st")},
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
            {"grade": "Close Fail", "marks": _calculate_mark_for_grade(max_marks, 0.30, "Fail")},
            {"grade": "Fail", "marks": _calculate_mark_for_grade(max_marks, 0.20, "Fail")},
            {"grade": "Poor Fail", "marks": _calculate_mark_for_grade(max_marks, 0.10, "Fail")},
            {"grade": "Zero Fail", "marks": _calculate_mark_for_grade(max_marks, 0.00, "Fail")},
        ]
    
    return bands
