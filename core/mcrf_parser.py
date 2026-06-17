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

    # --- Year, Period, Occurrence, Credits ---
    # Standard MCRF layout: Year=row8/colC, Period=row9/colC, Occurrence=row10/colC (0-indexed: rows 7,8,9)
    # Credits=row8/colE (0-indexed: row 7, col 4)
    year = ""
    period = ""
    occurrence = ""
    credits_val = 20

    def _cell(row_idx, col_idx):
        if len(rows) > row_idx and len(rows[row_idx]) > col_idx:
            v = rows[row_idx][col_idx]
            return str(v).strip() if v is not None else ""
        return ""

    # Try canonical positions first
    year_raw = _cell(7, 2)
    period_raw = _cell(8, 2)
    occurrence_raw = _cell(9, 2)
    credits_raw = _cell(7, 4)

    # Validate by checking the labels in col A
    if str(rows[7][0]).strip().lower() == "year" if len(rows) > 7 and rows[7] else False:
        year = year_raw
    if len(rows) > 7 and len(rows[7]) > 3 and str(rows[7][3]).strip().lower() == "credits":
        try:
            credits_val = int(float(credits_raw)) if credits_raw else 20
        except ValueError:
            credits_val = 20

    if str(rows[8][0]).strip().lower() == "period" if len(rows) > 8 and rows[8] else False:
        period = period_raw
    if str(rows[9][0]).strip().lower() == "occurrence" if len(rows) > 9 and rows[9] else False:
        occurrence_raw_val = occurrence_raw
        # Extract just BNN/FNN code from e.g. "BNN: September start - Newcastle upon Tyne"
        occ_match = re.match(r'^([A-Z]{1,4}NN)\b', occurrence_raw_val, re.IGNORECASE)
        occurrence = occ_match.group(1).upper() if occ_match else occurrence_raw_val

    # Fallback: scan pre-header rows for labelled cells if not found
    for row in rows[:header_row_idx]:
        if not row:
            continue
        for col_idx, cell in enumerate(row):
            if not cell:
                continue
            label = str(cell).strip().lower()
            val = str(row[col_idx + 1]).strip() if col_idx + 1 < len(row) and row[col_idx + 1] is not None else ""
            if label == "year" and not year:
                year = val
            elif label == "period" and not period:
                period = val
            elif label == "occurrence" and not occurrence:
                occ_match = re.match(r'^([A-Z]{1,4}NN)\b', val, re.IGNORECASE)
                occurrence = occ_match.group(1).upper() if occ_match else val
            elif label == "credits":
                if val:
                    try:
                        val_clean = re.sub(r'[^\d.]', '', val)
                        credits_val = int(float(val_clean))
                    except ValueError:
                        pass

    return headers, data_rows, is_mcrf, {
        "module_code": module_code,
        "module_title": module_title,
        "comp_names_map": comp_names_map,
        "year": year,
        "period": period,
        "occurrence": occurrence,
        "credits": credits_val,
        "detected_credits": credits_val,
    }
