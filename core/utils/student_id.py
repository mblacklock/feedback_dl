import re

def format_student_id(raw_id):
    """
    Format a student ID to Northumbria's standard: w12345678.
    Extracts the first sequence of exactly 8 digits and prefixes with 'w'.
    If no 8-digit sequence is found, returns the cleaned original string.
    """
    if raw_id is None:
        return ""
    s_id = str(raw_id).strip()
    match = re.search(r'\d{8}', s_id)
    if match:
        return f"w{match.group(0)}"
    return s_id
