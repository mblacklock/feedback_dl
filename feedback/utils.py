"""Utility functions for grade band calculations."""
from math import floor


def _round_marks(value):
    """Traditional rounding (always round 0.5 up) for grade marks."""
    return int(floor(value + 0.5))


def validate_subdivision(max_marks, subdivision):
    """
    Check if a subdivision produces valid (strictly decreasing) grade bands.
    
    Returns True if valid, False if bands would overlap/violate grade hierarchy.
    
    Args:
        max_marks: Maximum marks for the category
        subdivision: "none", "high_low", or "high_mid_low"
    
    Returns:
        bool: True if subdivision produces strictly decreasing marks
    """
    bands = calculate_grade_bands(max_marks, subdivision)
    
    # Check that marks are strictly decreasing
    for i in range(1, len(bands)):
        if bands[i]["marks"] >= bands[i-1]["marks"]:
            return False
    
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
        # No subdivision - use midpoint of each band
        # 1st: 85% (midpoint of 70-100%)
        # 2:1: 65% (midpoint of 60-69%)
        # 2:2: 55% (midpoint of 50-59%)
        # 3rd: 45% (midpoint of 40-49%)
        # Fail: 20% (midpoint of 0-39%)
        bands = [
            {"grade": "1st", "marks": _round_marks(max_marks * 0.85)},
            {"grade": "2:1", "marks": _round_marks(max_marks * 0.65)},
            {"grade": "2:2", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "3rd", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
    elif subdivision == "high_low":
        # High/Low subdivision - use 85% and 75% for High/Low of each band
        # High 1st: 85%, Low 1st: 75%
        # High 2:1: 65%, Low 2:1: 55%
        # High 2:2: 55%, Low 2:2: 45%
        # High 3rd: 45%, Low 3rd: 35%
        # Fail: 20%
        bands = [
            {"grade": "High 1st", "marks": _round_marks(max_marks * 0.85)},
            {"grade": "Low 1st", "marks": _round_marks(max_marks * 0.75)},
            {"grade": "High 2:1", "marks": _round_marks(max_marks * 0.65)},
            {"grade": "Low 2:1", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "High 2:2", "marks": _round_marks(max_marks * 0.55)},
            {"grade": "Low 2:2", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "High 3rd", "marks": _round_marks(max_marks * 0.45)},
            {"grade": "Low 3rd", "marks": _round_marks(max_marks * 0.35)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
    elif subdivision == "high_mid_low":
        # High/Mid/Low subdivision - use 90%, 80%, 70% etc for High/Mid/Low of each band
        # High 1st: 90%, Mid 1st: 80%, Low 1st: 70%
        # High 2:1: 67%, Mid 2:1: 63%, Low 2:1: 60%
        # High 2:2: 57%, Mid 2:2: 53%, Low 2:2: 50%
        # High 3rd: 47%, Mid 3rd: 43%, Low 3rd: 40%
        # Fail: 20%
        bands = [
            {"grade": "High 1st", "marks": _round_marks(max_marks * 0.90)},
            {"grade": "Mid 1st", "marks": _round_marks(max_marks * 0.80)},
            {"grade": "Low 1st", "marks": _round_marks(max_marks * 0.70)},
            {"grade": "High 2:1", "marks": _round_marks(max_marks * 0.67)},
            {"grade": "Mid 2:1", "marks": _round_marks(max_marks * 0.63)},
            {"grade": "Low 2:1", "marks": _round_marks(max_marks * 0.60)},
            {"grade": "High 2:2", "marks": _round_marks(max_marks * 0.57)},
            {"grade": "Mid 2:2", "marks": _round_marks(max_marks * 0.53)},
            {"grade": "Low 2:2", "marks": _round_marks(max_marks * 0.50)},
            {"grade": "High 3rd", "marks": _round_marks(max_marks * 0.47)},
            {"grade": "Mid 3rd", "marks": _round_marks(max_marks * 0.43)},
            {"grade": "Low 3rd", "marks": _round_marks(max_marks * 0.40)},
            {"grade": "Fail", "marks": _round_marks(max_marks * 0.20)},
        ]
    
    return bands
