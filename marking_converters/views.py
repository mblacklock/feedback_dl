import csv
import io
import re
import base64
import openpyxl
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages

from core.utils.student_id import format_student_id

# ── ID Normalization Helper ──
def normalize_id(id_val):
    if id_val is None:
        return ""
    
    # Clean leading/trailing spaces and non-breaking spaces
    s = str(id_val).replace('\xa0', ' ').strip().lower()
    
    # Try using format_student_id (standardizes exactly 8 digits to e.g. 'w12345678')
    formatted = format_student_id(s)
    if formatted.startswith('w') and len(formatted) == 9 and formatted[1:].isdigit():
        return formatted[1:]  # Extract raw 8-digit sequence '12345678'
        
    # Extract longest sequence of digits of length >= 5
    matches = re.findall(r'\d+', s)
    if matches:
        matches.sort(key=len, reverse=True)
        longest = matches[0]
        if len(longest) >= 5:
            if len(longest) >= 8:
                return longest[-8:]  # Target standard 8 digits
            return longest
            
    # Fallback: strip exact non-alphanumeric special characters
    return re.sub(r'[^a-z0-9]', '', s)


# ── File Parsing Helper ──
def read_uploaded_file(file):
    """Reads CSV, XLSX, or XLS from upload and returns (headers, rows)."""
    filename = file.name.lower()
    
    file_bytes = file.read()
    file.seek(0)
    
    # Check for UTF-16 BOM (common for database or Blackboard exports named as .xls or .csv)
    is_utf16 = file_bytes.startswith(b'\xff\xfe') or file_bytes.startswith(b'\xfe\xff')
    
    if is_utf16 or filename.endswith('.csv'):
        try:
            encoding = 'utf-16' if is_utf16 else 'utf-8'
            content = file_bytes.decode(encoding, errors='replace').splitlines()
            dialect = 'excel-tab' if content and '\t' in content[0] else 'excel'
            reader = csv.reader(content, dialect=dialect)
            aoa = list(reader)
        except Exception as e:
            raise ValueError(f"Could not parse text/CSV file: {str(e)}")
    else:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            aoa = []
            for row in ws.iter_rows(values_only=True):
                aoa.append(list(row))
        except Exception:
            try:
                import xlrd
                wb = xlrd.open_workbook(file_contents=file_bytes)
                ws = wb.sheet_by_index(0)
                aoa = []
                for i in range(ws.nrows):
                    aoa.append(ws.row_values(i))
            except Exception as xl_err:
                # Attempt plain text CSV fallback if it is a tab-separated text export without a BOM
                try:
                    content = file_bytes.decode('utf-8', errors='replace').splitlines()
                    dialect = 'excel-tab' if content and '\t' in content[0] else 'excel'
                    reader = csv.reader(content, dialect=dialect)
                    aoa = list(reader)
                except Exception:
                    raise ValueError(f"Spreadsheet format not recognized or corrupted: {str(xl_err)}")
            
    # Locate header row index
    header_idx = 0
    is_mcrf = False
    
    for i, row in enumerate(aoa[:50]):
        if not row:
            continue
        row_str = " ".join(str(val) for val in row if val is not None).lower()
        if "module marks record form" in row_str:
            is_mcrf = True
        if "student id" in row_str or "student no" in row_str or ("username" in row_str and "last name" in row_str):
            header_idx = i
            break
            
    # If it is MCRF with multi-row headers, merge them for clearer display
    if is_mcrf and header_idx > 0:
        parent_row = aoa[header_idx - 1]
        main_row = aoa[header_idx]
        current_parent = ''
        
        for c in range(len(main_row)):
            p_val = str(parent_row[c] or '').strip() if c < len(parent_row) else ''
            if p_val != '':
                current_parent = p_val
                
            m_val = str(main_row[c] or '').strip() if c < len(main_row) else ''
            if m_val and current_parent and current_parent != m_val:
                if any(x in m_val.lower() for x in ['mark', 'grad', 'result']):
                    main_row[c] = f"{current_parent} - {m_val}"
        aoa[header_idx] = main_row

    headers = [str(h).strip() if h is not None else "" for h in aoa[header_idx]]
    
    # Make headers unique
    unique_headers = []
    seen = {}
    for h in headers:
        if not h:
            h = "Unnamed"
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)
            
    rows = []
    for row in aoa[header_idx+1:]:
        if not any(row is not None and str(row).strip() != '' for row in row):
            continue
        row_dict = {}
        for col_idx, h in enumerate(unique_headers):
            if col_idx < len(row):
                val = row[col_idx]
                row_dict[h] = "" if val is None else str(val).strip()
            else:
                row_dict[h] = ""
        rows.append(row_dict)
        
    return unique_headers, rows


# ── Dashboard landing view ──
def dashboard(request):
    return render(request, "marking_converters/dashboard.html")


# ── Gradebook Merger: Step 1 (Upload) ──
def merge_upload(request):
    if request.method == "POST":
        marks_file = request.FILES.get("marks_file")
        bb_file = request.FILES.get("bb_file")
        
        if not marks_file or not bb_file:
            messages.error(request, "Please upload both files.")
            return render(request, "marking_converters/merge_upload.html")
            
        try:
            local_headers, local_rows = read_uploaded_file(marks_file)
            bb_headers, bb_rows = read_uploaded_file(bb_file)
            
            # Store in session
            request.session["converter_local_headers"] = local_headers
            request.session["converter_local_rows"] = local_rows
            request.session["converter_bb_headers"] = bb_headers
            request.session["converter_bb_rows"] = bb_rows
            
            return redirect("converter_merge_match")
        except Exception as e:
            messages.error(request, f"Error parsing files: {str(e)}")
            
    return render(request, "marking_converters/merge_upload.html")


# ── Gradebook Merger: Step 2 (Match & Download) ──
def merge_match(request):
    local_headers = request.session.get("converter_local_headers")
    local_rows = request.session.get("converter_local_rows")
    bb_headers = request.session.get("converter_bb_headers")
    bb_rows = request.session.get("converter_bb_rows")
    
    if local_headers is None or local_rows is None or bb_headers is None or bb_rows is None:
        messages.error(request, "Session expired or upload data missing. Please upload files again.")
        return redirect("converter_merge_upload")
        
    # Determine defaults: prioritize username over student id
    def get_id_default(headers):
        for h in headers:
            hl = h.lower()
            if "username" in hl or "user name" in hl:
                return h
        for h in headers:
            hl = h.lower()
            if "student id" in hl or "student no" in hl or "student_id" in hl or "student" in hl:
                return h
        return ""

    local_id_default = get_id_default(local_headers)
    bb_id_default = get_id_default(bb_headers)
    
    if request.method == "POST":
        local_id_col = request.POST.get("local_id_col")
        bb_id_col = request.POST.get("bb_id_col")
        
        # Parse dynamically populated column mappings
        mappings = []
        for key in request.POST.keys():
            if key.startswith("map_local_"):
                suffix = key[len("map_local_"):]
                local_col = request.POST.get(key)
                bb_col = request.POST.get(f"map_bb_{suffix}")
                if local_col and bb_col:
                    mappings.append((local_col, bb_col))
                    
        if not local_id_col or not bb_id_col or not mappings:
            messages.error(request, "Please configure ID columns and at least one grade mapping.")
            return render(request, "marking_converters/merge_match.html", {
                "local_headers": local_headers,
                "bb_headers": bb_headers,
                "local_id_default": local_id_default,
                "bb_id_default": bb_id_default
            })
            
        # Perform merge
        marks_dict = {}
        for row in local_rows:
            id_val = row.get(local_id_col)
            if id_val:
                normalized = normalize_id(id_val)
                marks_dict[normalized] = row
                
        match_count = 0
        missing_count = 0
        
        # Update Blackboard gradebook data in-memory
        for row in bb_rows:
            id_val = row.get(bb_id_col)
            if id_val:
                normalized = normalize_id(id_val)
                if normalized in marks_dict:
                    marks_row = marks_dict[normalized]
                    for local_col, bb_col in mappings:
                        row[bb_col] = marks_row.get(local_col, "")
                    match_count += 1
                else:
                    missing_count += 1
                    
        if match_count == 0:
            messages.error(request, "Zero matching student IDs found. Please check your column selections.")
            return render(request, "marking_converters/merge_match.html", {
                "local_headers": local_headers,
                "bb_headers": bb_headers,
                "local_id_default": local_id_default,
                "bb_id_default": bb_id_default
            })
            
        # Create CSV download response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="Merged_Blackboard_Gradebook.csv"'
        
        # Write CSV with correct headers
        writer = csv.DictWriter(response, fieldnames=bb_headers)
        writer.writeheader()
        for row in bb_rows:
            writer.writerow(row)
            
        return response
        
    return render(request, "marking_converters/merge_match.html", {
        "local_headers": local_headers,
        "bb_headers": bb_headers,
        "local_id_default": local_id_default,
        "bb_id_default": bb_id_default
    })


# ── MCRF Populator: Step 1 (Upload) ──
def populate_upload(request):
    if request.method == "POST":
        marks_file = request.FILES.get("marks_file")
        mcrf_file = request.FILES.get("mcrf_file")
        
        if not marks_file or not mcrf_file:
            messages.error(request, "Please upload both files.")
            return render(request, "marking_converters/populate_upload.html")
            
        try:
            local_headers, local_rows = read_uploaded_file(marks_file)
            mcrf_headers, mcrf_rows = read_uploaded_file(mcrf_file)
            
            # Store template workbook as base64 in session to retain styles
            mcrf_file.seek(0)
            request.session["converter_mcrf_template"] = base64.b64encode(mcrf_file.read()).decode('utf-8')
            request.session["converter_mcrf_name"] = mcrf_file.name
            
            request.session["converter_local_headers"] = local_headers
            request.session["converter_local_rows"] = local_rows
            request.session["converter_mcrf_headers"] = mcrf_headers
            request.session["converter_mcrf_rows"] = mcrf_rows
            
            return redirect("converter_populate_match")
        except Exception as e:
            messages.error(request, f"Error parsing files: {str(e)}")
            
    return render(request, "marking_converters/populate_upload.html")


# ── MCRF Populator: Step 2 (Match & Download) ──
def populate_match(request):
    local_headers = request.session.get("converter_local_headers")
    local_rows = request.session.get("converter_local_rows")
    mcrf_headers = request.session.get("converter_mcrf_headers")
    mcrf_rows = request.session.get("converter_mcrf_rows")
    mcrf_template = request.session.get("converter_mcrf_template")
    mcrf_name = request.session.get("converter_mcrf_name", "Populated_MCRF.xlsx")
    
    if local_headers is None or local_rows is None or mcrf_headers is None or mcrf_rows is None or mcrf_template is None:
        messages.error(request, "Session expired or upload data missing. Please upload files again.")
        return redirect("converter_populate_upload")
        
    # Determine defaults: prioritize username over student id
    def get_id_default(headers):
        for h in headers:
            hl = h.lower()
            if "username" in hl or "user name" in hl:
                return h
        for h in headers:
            hl = h.lower()
            if "student id" in hl or "student no" in hl or "student_id" in hl or "student" in hl:
                return h
        return ""

    local_id_default = get_id_default(local_headers)
    mcrf_id_default = get_id_default(mcrf_headers)
    
    mcrf_mark_headers = [h for h in mcrf_headers if "mark" in h.lower()]
    if not mcrf_mark_headers:
        mcrf_mark_headers = mcrf_headers
    
    if request.method == "POST":
        local_id_col = request.POST.get("local_id_col")
        mcrf_id_col = request.POST.get("mcrf_id_col")
        
        # Mappings of local column names to MCRF template column names
        mappings = []
        for key in request.POST.keys():
            if key.startswith("map_local_"):
                suffix = key[len("map_local_"):]
                local_col = request.POST.get(key)
                mcrf_col = request.POST.get(f"map_mcrf_{suffix}")
                if local_col and mcrf_col:
                    mappings.append((local_col, mcrf_col))
                    
        if not local_id_col or not mcrf_id_col or not mappings:
            messages.error(request, "Please configure ID columns and at least one grade mapping.")
            return render(request, "marking_converters/populate_match.html", {
                "local_headers": local_headers,
                "mcrf_headers": mcrf_headers,
                "mcrf_mark_headers": mcrf_mark_headers,
                "local_id_default": local_id_default,
                "mcrf_id_default": mcrf_id_default
            })
            
        try:
            # Decode the original MCRF template workbook
            workbook_data = base64.b64decode(mcrf_template)
            
            is_xls = mcrf_name.lower().endswith('.xls')
            
            if is_xls:
                # XLS Flow using xlrd & xlutils filter to preserve 100% of formatting and styles
                import xlrd
                from xlutils.filter import process, XLRDReader, XLWTWriter
                
                xls_wb = xlrd.open_workbook(file_contents=workbook_data, formatting_info=True)
                xls_ws = xls_wb.sheet_by_index(0)
                
                writer = XLWTWriter()
                process(XLRDReader(xls_wb, 'unknown.xls'), writer)
                wb = writer.output[0][1]
                styles = writer.style_list
                ws = wb.get_sheet(0)
                
                aoa = []
                for r in range(xls_ws.nrows):
                    aoa.append(xls_ws.row_values(r))
                    
                # Scan to find header row index
                header_idx = 0
                for i, row in enumerate(aoa[:50]):
                    if not row:
                        continue
                    row_str = " ".join(str(val) for val in row if val is not None).lower()
                    if "student id" in row_str or "student no" in row_str:
                        header_idx = i
                        break
                        
                header_cells = aoa[header_idx]
                mcrf_col_indices = {}
                seen = {}
                for col_idx, h in enumerate(header_cells):
                    if h is None or str(h).strip() == "":
                        continue
                    h_clean = str(h).strip()
                    if h_clean in seen:
                        seen[h_clean] += 1
                        mcrf_col_indices[f"{h_clean}_{seen[h_clean]}"] = col_idx
                    else:
                        seen[h_clean] = 0
                        mcrf_col_indices[h_clean] = col_idx
                        
                if header_idx > 0:
                    parent_row = aoa[header_idx - 1]
                    current_parent = ''
                    for col_idx, h in enumerate(header_cells):
                        p_val = str(parent_row[col_idx] or '').strip() if col_idx < len(parent_row) else ''
                        if p_val != '':
                            current_parent = p_val
                        m_val = str(h or '').strip()
                        if m_val and current_parent and current_parent != m_val:
                            if any(x in m_val.lower() for x in ['mark', 'grad', 'result']):
                                mcrf_col_indices[f"{current_parent} - {m_val}"] = col_idx
            else:
                # XLSX Flow using openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(workbook_data))
                ws = wb.active
                
                aoa = []
                for row in ws.iter_rows(values_only=True):
                    aoa.append(list(row))
                    
                # Scan to find header row index
                header_idx = 0
                for i, row in enumerate(aoa[:50]):
                    if not row:
                        continue
                    row_str = " ".join(str(val) for val in row if val is not None).lower()
                    if "student id" in row_str or "student no" in row_str:
                        header_idx = i
                        break
                        
                header_cells = aoa[header_idx]
                mcrf_col_indices = {}
                seen = {}
                for col_idx, h in enumerate(header_cells):
                    if h is None or str(h).strip() == "":
                        continue
                    h_clean = str(h).strip()
                    if h_clean in seen:
                        seen[h_clean] += 1
                        mcrf_col_indices[f"{h_clean}_{seen[h_clean]}"] = col_idx + 1
                    else:
                        seen[h_clean] = 0
                        mcrf_col_indices[h_clean] = col_idx + 1
                        
                if header_idx > 0:
                    parent_row = aoa[header_idx - 1]
                    current_parent = ''
                    for col_idx, h in enumerate(header_cells):
                        p_val = str(parent_row[col_idx] or '').strip() if col_idx < len(parent_row) else ''
                        if p_val != '':
                            current_parent = p_val
                        m_val = str(h or '').strip()
                        if m_val and current_parent and current_parent != m_val:
                            if any(x in m_val.lower() for x in ['mark', 'grad', 'result']):
                                mcrf_col_indices[f"{current_parent} - {m_val}"] = col_idx + 1
                                
            # Match local student IDs to their rows
            marks_dict = {}
            for row in local_rows:
                id_val = row.get(local_id_col)
                if id_val:
                    normalized = normalize_id(id_val)
                    marks_dict[normalized] = row
                    
            # Locate Student ID column index in template
            mcrf_id_col_idx = mcrf_col_indices.get(mcrf_id_col)
            if mcrf_id_col_idx is None:
                messages.error(request, "Could not map MCRF Student ID column index in workbook.")
                return render(request, "marking_converters/populate_match.html", {
                    "local_headers": local_headers,
                    "mcrf_headers": mcrf_headers,
                    "mcrf_mark_headers": mcrf_mark_headers,
                    "local_id_default": local_id_default,
                    "mcrf_id_default": mcrf_id_default
                })
                
            match_count = 0
            
            # Populate workbook data
            if is_xls:
                # 0-indexed writing for xlwt
                for r_idx in range(header_idx + 1, len(aoa)):
                    cell_id_val = aoa[r_idx][mcrf_id_col_idx]
                    if cell_id_val:
                        normalized = normalize_id(cell_id_val)
                        if normalized in marks_dict:
                            marks_row = marks_dict[normalized]
                            for local_col, mcrf_col in mappings:
                                col_idx = mcrf_col_indices.get(mcrf_col)
                                if col_idx is not None:
                                    val_to_write = marks_row.get(local_col, "")
                                    try:
                                        if val_to_write.strip() != "":
                                            if '.' in val_to_write:
                                                val_to_write = float(val_to_write)
                                            else:
                                                val_to_write = int(val_to_write)
                                    except ValueError:
                                        pass
                                    
                                    # Retrieve and preserve the original cell style/borders
                                    try:
                                        xf_index = xls_ws.cell_xf_index(r_idx, col_idx)
                                        cell_style = styles[xf_index]
                                    except Exception:
                                        cell_style = None
                                        
                                    if cell_style is not None:
                                        ws.write(r_idx, col_idx, val_to_write, cell_style)
                                    else:
                                        ws.write(r_idx, col_idx, val_to_write)
                            match_count += 1
            else:
                # 1-indexed writing for openpyxl
                for r_idx in range(header_idx + 2, len(aoa) + 1):
                    cell_id_val = ws.cell(row=r_idx, column=mcrf_id_col_idx).value
                    if cell_id_val:
                        normalized = normalize_id(cell_id_val)
                        if normalized in marks_dict:
                            marks_row = marks_dict[normalized]
                            for local_col, mcrf_col in mappings:
                                col_idx = mcrf_col_indices.get(mcrf_col)
                                if col_idx:
                                    val_to_write = marks_row.get(local_col, "")
                                    try:
                                        if val_to_write.strip() != "":
                                            if '.' in val_to_write:
                                                val_to_write = float(val_to_write)
                                            else:
                                                val_to_write = int(val_to_write)
                                    except ValueError:
                                        pass
                                    ws.cell(row=r_idx, column=col_idx, value=val_to_write)
                            match_count += 1
                            
            if match_count == 0:
                sample_local = []
                for row in local_rows[:5]:
                    id_val = row.get(local_id_col)
                    sample_local.append(f"'{id_val}' -> '{normalize_id(id_val)}'")
                    
                sample_template = []
                scanned_rows = 0
                if is_xls:
                    for r_idx in range(header_idx + 1, len(aoa)):
                        cell_id_val = aoa[r_idx][mcrf_id_col_idx]
                        if cell_id_val is not None and str(cell_id_val).strip() != "":
                            sample_template.append(f"'{cell_id_val}' -> '{normalize_id(cell_id_val)}'")
                            if len(sample_template) >= 5:
                                break
                        scanned_rows += 1
                else:
                    for r_idx in range(header_idx + 2, len(aoa) + 1):
                        cell_id_val = ws.cell(row=r_idx, column=mcrf_id_col_idx).value
                        if cell_id_val is not None and str(cell_id_val).strip() != "":
                            sample_template.append(f"'{cell_id_val}' -> '{normalize_id(cell_id_val)}'")
                            if len(sample_template) >= 5:
                                break
                        scanned_rows += 1
                            
                debug_info = (
                    f"Diagnostics - Scanned {scanned_rows} template rows. "
                    f"Selected Column: '{mcrf_id_col}' (Excel Col {mcrf_id_col_idx + (0 if is_xls else 1)}). "
                    f"Sample Local IDs: [{', '.join(sample_local)}]. "
                    f"Sample Template IDs: [{', '.join(sample_template)}]."
                )
                messages.error(request, f"Zero student IDs successfully matched inside the MCRF template sheet. {debug_info}")
                return render(request, "marking_converters/populate_match.html", {
                    "local_headers": local_headers,
                    "mcrf_headers": mcrf_headers,
                    "mcrf_mark_headers": mcrf_mark_headers,
                    "local_id_default": local_id_default,
                    "mcrf_id_default": mcrf_id_default
                })
                
            # Create download response
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            # Set response headers
            if is_xls:
                out_filename = mcrf_name.rsplit('.', 1)[0] + "_Populated.xls"
                response = HttpResponse(
                    output.read(),
                    content_type='application/vnd.ms-excel'
                )
            else:
                out_filename = mcrf_name.rsplit('.', 1)[0] + "_Populated.xlsx"
                response = HttpResponse(
                    output.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            response['Content-Disposition'] = f'attachment; filename="{out_filename}"'
            return response
            
        except Exception as e:
            messages.error(request, f"Error writing marks to workbook: {str(e)}")
            
    return render(request, "marking_converters/populate_match.html", {
        "local_headers": local_headers,
        "mcrf_headers": mcrf_headers,
        "mcrf_mark_headers": mcrf_mark_headers,
        "local_id_default": local_id_default,
        "mcrf_id_default": mcrf_id_default
    })
