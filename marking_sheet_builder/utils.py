import io
import json
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation

from core.utils.grade_bands import calculate_grade_bands


ALLOWED_COLUMN_TYPES = {
    "numeric": "Numeric mark",
    "rubric": "Rubric mark",
    "information": "Information",
    "feedback": "Feedback comment",
}
ALLOWED_SUBDIVISIONS = {"none", "high_low", "high_mid_low"}
ALLOWED_DEGREE_LEVELS = {"BEng", "MEng/MSc"}


def parse_builder_payload(raw_payload):
    try:
        payload = json.loads(raw_payload or "{}")
    except json.JSONDecodeError:
        payload = {}

    name_mode = payload.get("name_mode")
    if name_mode not in {"full", "split"}:
        name_mode = "full"

    degree_level = payload.get("degree_level")
    if degree_level not in ALLOWED_DEGREE_LEVELS:
        degree_level = "BEng"

    rows = _parse_positive_int(payload.get("rows"), default=100, maximum=500)
    max_mark = _parse_positive_int(payload.get("max_mark"), default=100, maximum=10000)

    boundaries = _clean_lines(payload.get("rubric_boundaries"))
    if not boundaries:
        boundaries = ["First", "Upper second", "Lower second", "Third", "Fail"]

    columns = []
    for item in payload.get("columns", []):
        column_type = item.get("type")
        if column_type not in ALLOWED_COLUMN_TYPES:
            continue
        title = _clean_title(item.get("title")) or ALLOWED_COLUMN_TYPES[column_type]
        column = {"type": column_type, "title": title}
        if column_type in {"numeric", "rubric"}:
            column["max_mark"] = _parse_positive_int(
                item.get("max_mark"), default=max_mark, maximum=10000
            )
        if column_type == "rubric":
            subdivision = item.get("subdivision")
            if subdivision not in ALLOWED_SUBDIVISIONS:
                subdivision = "none"
            column["subdivision"] = subdivision
        columns.append(column)

    if not columns:
        columns = [{"type": "numeric", "title": "Mark", "max_mark": max_mark}]

    return {
        "name_mode": name_mode,
        "degree_level": degree_level,
        "rows": rows,
        "max_mark": max_mark,
        "rubric_boundaries": boundaries,
        "columns": columns,
    }


def validate_builder_config(config):
    assessed_total = sum(
        column.get("max_mark", 0)
        for column in config["columns"]
        if column["type"] in {"numeric", "rubric"}
    )
    if assessed_total != config["max_mark"]:
        return [
            f"Mark and rubric column maxima must add up to {config['max_mark']}. "
            f"They currently add up to {assessed_total}."
        ]
    return []


def build_marking_workbook(config):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Marking Sheet"

    rubric_sheet = workbook.create_sheet("Rubric Boundaries")
    _write_rubric_boundaries(rubric_sheet, config)
    rubric_sheet.sheet_state = "hidden"

    headers = ["Student ID"]
    if config["name_mode"] == "split":
        headers.extend(["Last Name", "First Name"])
    else:
        headers.append("Student Name")
    headers.extend(_display_column_title(column) for column in config["columns"])
    headers.append(f"Mark ({config['max_mark']})")
    headers.append("%")

    sheet.append(headers)
    data_rows = config["rows"]
    total_columns = len(headers)
    for _ in range(data_rows):
        sheet.append([""] * total_columns)

    _write_calculated_result_formulas(sheet, config, data_rows, total_columns)
    _style_marking_sheet(sheet, headers, data_rows)
    _apply_validations(sheet, config, data_rows)

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _apply_validations(sheet, config, data_rows):
    first_marking_col = 3 if config["name_mode"] == "full" else 4
    for offset, column in enumerate(config["columns"]):
        excel_col = get_column_letter(first_marking_col + offset)
        cell_range = f"{excel_col}2:{excel_col}{data_rows + 1}"
        if column["type"] == "numeric":
            validation = DataValidation(
                type="decimal",
                operator="between",
                formula1=0,
                formula2=column["max_mark"],
                allow_blank=True,
            )
            validation.error = f"Enter a number from 0 to {column['max_mark']}."
            validation.errorTitle = "Invalid mark"
            sheet.add_data_validation(validation)
            validation.add(cell_range)
        elif column["type"] == "rubric":
            rubric_boundaries = calculate_grade_bands(
                column["max_mark"],
                column.get("subdivision", "none"),
                degree_level=config.get("degree_level", "BEng"),
            )
            rubric_label_col, _ = _rubric_sheet_columns_for(config["columns"], offset)
            rubric_range = (
                f"{quote_sheetname('Rubric Boundaries')}!"
                f"${rubric_label_col}$2:${rubric_label_col}${len(rubric_boundaries) + 1}"
            )
            validation = DataValidation(
                type="list",
                formula1=rubric_range,
                allow_blank=True,
            )
            validation.error = "Choose one of the generated rubric boundaries."
            validation.errorTitle = "Invalid rubric boundary"
            sheet.add_data_validation(validation)
            validation.add(cell_range)


def _style_marking_sheet(sheet, headers, data_rows):
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D9E2F3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in sheet.iter_rows(min_row=2, max_row=data_rows + 1, max_col=len(headers)):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    widths = {
        "Student ID": 16,
        "Student Name": 26,
        "Last Name": 20,
        "First Name": 20,
    }
    for index, header in enumerate(headers, start=1):
        width = widths.get(header, 24)
        if re.search(r"feedback|comment", header, re.IGNORECASE):
            width = 42
        sheet.column_dimensions[get_column_letter(index)].width = width

    sheet.freeze_panes = "A2"


def _write_calculated_result_formulas(sheet, config, data_rows, total_columns):
    first_marking_col = 3 if config["name_mode"] == "full" else 4
    mark_col = get_column_letter(total_columns - 1)
    percent_col = get_column_letter(total_columns)
    assessed_offsets = [
        (offset, column)
        for offset, column in enumerate(config["columns"])
        if column["type"] in {"numeric", "rubric"}
    ]

    for row_index in range(2, data_rows + 2):
        terms = []
        presence_checks = []
        for offset, column in assessed_offsets:
            source_col = get_column_letter(first_marking_col + offset)
            source_cell = f"{source_col}{row_index}"
            presence_checks.append(f'{source_cell}<>""')
            if column["type"] == "numeric":
                terms.append(f"N({source_cell})")
            elif column["type"] == "rubric":
                label_col, marks_col = _rubric_sheet_columns_for(config["columns"], offset)
                band_count = len(
                    calculate_grade_bands(
                        column["max_mark"],
                        column.get("subdivision", "none"),
                        degree_level=config.get("degree_level", "BEng"),
                    )
                )
                lookup_range = (
                    f"{quote_sheetname('Rubric Boundaries')}!"
                    f"${label_col}$2:${marks_col}${band_count + 1}"
                )
                terms.append(f"IFERROR(VLOOKUP({source_cell},{lookup_range},2,FALSE),0)")

        if not terms:
            sheet[f"{mark_col}{row_index}"] = '=""'
            sheet[f"{percent_col}{row_index}"] = '=""'
            continue

        formula = f'=IF(OR({",".join(presence_checks)}),{"+".join(terms)},"")'
        sheet[f"{mark_col}{row_index}"] = formula
        sheet[f"{percent_col}{row_index}"] = (
            f'=IF({mark_col}{row_index}<>"",{mark_col}{row_index}/{config["max_mark"]},"")'
        )
        sheet[f"{percent_col}{row_index}"].number_format = "0%"


def _display_column_title(column):
    if column["type"] in {"numeric", "rubric"}:
        return f"{column['title']} ({column['max_mark']})"
    return column["title"]


def _write_rubric_boundaries(sheet, config):
    rubric_columns = [
        column for column in config["columns"] if column["type"] == "rubric"
    ]
    if not rubric_columns:
        sheet["A1"] = "Rubric Boundary"
        for index, boundary in enumerate(config["rubric_boundaries"], start=2):
            sheet.cell(row=index, column=1, value=boundary)
        sheet.column_dimensions["A"].width = 28
        return

    for rubric_index, column in enumerate(rubric_columns):
        label_col_index = (rubric_index * 2) + 1
        marks_col_index = label_col_index + 1
        label_excel_col = get_column_letter(label_col_index)
        marks_excel_col = get_column_letter(marks_col_index)
        sheet.cell(row=1, column=label_col_index, value=column["title"])
        sheet.cell(row=1, column=marks_col_index, value=f"{column['title']} marks")
        for header_cell in (
            sheet.cell(row=1, column=label_col_index),
            sheet.cell(row=1, column=marks_col_index),
        ):
            header_cell.font = Font(bold=True, color="FFFFFF")
            header_cell.fill = PatternFill("solid", fgColor="1F4E79")

        bands = calculate_grade_bands(
            column["max_mark"],
            column.get("subdivision", "none"),
            degree_level=config.get("degree_level", "BEng"),
        )
        for row_index, band in enumerate(bands, start=2):
            sheet.cell(row=row_index, column=label_col_index, value=band["grade"])
            sheet.cell(row=row_index, column=marks_col_index, value=band["marks"])
        sheet.column_dimensions[label_excel_col].width = 28
        sheet.column_dimensions[marks_excel_col].width = 14


def _rubric_sheet_columns_for(columns, marking_offset):
    rubric_index = 0
    for offset, column in enumerate(columns):
        if column["type"] != "rubric":
            continue
        if offset == marking_offset:
            label_col = get_column_letter((rubric_index * 2) + 1)
            marks_col = get_column_letter((rubric_index * 2) + 2)
            return label_col, marks_col
        rubric_index += 1
    return "A", "B"


def _clean_lines(value):
    if isinstance(value, list):
        candidates = value
    else:
        candidates = str(value or "").splitlines()
    return [_clean_title(item) for item in candidates if _clean_title(item)]


def _clean_title(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:80]


def _parse_positive_int(value, default, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))
