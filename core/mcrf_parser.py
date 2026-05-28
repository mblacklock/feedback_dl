import io
import re
import openpyxl
from openpyxl.utils import get_column_letter

MODULE_CODE_RE = re.compile(r'^([A-Z]{2,6}\d{3,5}[A-Z]?)\s*[-:–]?\s*(.*)$')

def parse_mcrf_workbook(file_file):
    """
    Parses a spreadsheet in-memory. Detects MCRF signature block
    and dynamically merges multi-row headings for clarity (e.g. "CW1" + "Mark" -> "CW1 - Mark").
    Supports modern .xlsx (via openpyxl) and legacy .xls (via xlrd).
    """
    file_bytes = file_file.read()
    file_file.seek(0)
    
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        try:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file_bytes)
            ws = wb.sheet_by_index(0)
            rows = [ws.row_values(i) for i in range(ws.nrows)]
        except Exception as e:
            raise ValueError(f"Spreadsheet format not recognized or corrupted: {str(e)}")
            
    if not rows or len(rows) < 2:
        raise ValueError("The uploaded spreadsheet is empty.")
        
    is_mcrf = False
    header_row_idx = 0
    
    # Scan first 50 rows to detect MCRF signatures and find the main header row
    for i in range(min(len(rows), 50)):
        row_cells = [str(c).strip() if c is not None else "" for c in rows[i]]
        row_text = " ".join(row_cells).lower()
        if "module marks record form" in row_text or "(mcrf)" in row_text:
            is_mcrf = True
            
        if any(keyword in cell.lower() for cell in row_cells for keyword in ["student id", "student no", "student number", "username"]):
            header_row_idx = i
            break
            
    raw_headers = [str(c).strip() if c is not None else "" for c in rows[header_row_idx]]
    headers = list(raw_headers)
    
    # Replace empty headers with '<Column X>'
    for idx in range(len(headers)):
        if not headers[idx]:
            headers[idx] = f"<Column {get_column_letter(idx + 1)}>"
            
    # If MCRF, merge parent and child headers
    if is_mcrf and header_row_idx > 0:
        parent_row = [str(c).strip() if c is not None else "" for c in rows[header_row_idx - 1]]
        current_parent = ""
        for c in range(len(headers)):
            p_val = parent_row[c] if c < len(parent_row) else ""
            if p_val != "":
                current_parent = p_val
                
            m_val = raw_headers[c] # Use raw header to verify original contents
            m_val_lower = m_val.lower()
            if m_val != "" and current_parent != "" and current_parent != m_val:
                if any(k in m_val_lower for k in ["mark", "grad", "result", "score"]):
                    headers[c] = f"{current_parent} - {m_val}"
                    
    # Read rows
    data_rows = []
    for r in rows[header_row_idx + 1:]:
        if any(cell is not None for cell in r):
            row_dict = {}
            for idx, cell in enumerate(r):
                if idx < len(headers):
                    h_name = headers[idx]
                    if h_name:
                        row_dict[h_name] = cell
            data_rows.append(row_dict)

    # --- Module details detection ---
    # Try C7 first (row 6, col 2) — the standard MCRF cell for module info.
    # If that's empty, scan pre-header rows for any cell matching a module code pattern.
    module_code = ""
    module_title = ""

    def _try_parse_module_cell(val):
        """Return (code, title) if val looks like a module details cell, else ('', '')."""
        if not val:
            return "", ""
        text = str(val).strip()
        m = MODULE_CODE_RE.match(text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return "", ""

    # 1. Try canonical MCRF position: row 7 (index 6), column C (index 2)
    if len(rows) > 6:
        c7_val = rows[6][2] if len(rows[6]) > 2 else None
        module_code, module_title = _try_parse_module_cell(c7_val)

    # 2. If not found, scan all pre-header rows for a matching cell
    if not module_code:
        for row in rows[:header_row_idx]:
            for cell in row:
                code, title = _try_parse_module_cell(cell)
                if code:
                    module_code, module_title = code, title
                    break
            if module_code:
                break

    # --- Assessment components mapping and descriptions scan ---
    comp_names_map = {}

    def normalize_comp_code(code_str):
        if not code_str:
            return ""
        s = str(code_str).strip().split('.')[0]
        if s.isdigit():
            return f"{int(s):03d}"
        return s.upper()

    # 1. Locate the row where Column A says "Component"
    component_row_idx = -1
    for idx, row in enumerate(rows[:header_row_idx]):
        if row and row[0] and str(row[0]).strip().lower() == "component":
            component_row_idx = idx
            break

    def clean_component_title(title):
        if not title:
            return ""
        # Remove parenthesized limits/durations (e.g. " (2500 words or equivalent)", " (3 hours)")
        cleaned = re.sub(
            r'\s*\([^)]*\b(words?|hrs?|hours?|mins?|minutes?)\b[^)]*\)',
            '',
            title,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(r'\s*\(\s*equivalent\s*\)', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip().rstrip(',').strip()

    # 2. Extract component codes (Col A) and titles (Col B) from rows directly below it
    if component_row_idx != -1:
        for row in rows[component_row_idx + 1:header_row_idx]:
            if row and row[0] is not None:
                code_val = str(row[0]).strip()
                if not code_val:
                    break
                code_norm = normalize_comp_code(code_val)
                if len(row) > 1 and row[1]:
                    title_clean = clean_component_title(str(row[1]).strip())
                    comp_names_map[code_norm] = title_clean

    return headers, data_rows, is_mcrf, {
        "module_code": module_code,
        "module_title": module_title,
        "comp_names_map": comp_names_map
    }
