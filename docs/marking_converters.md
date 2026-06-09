# Marking Converters

Two conversion tools for moving marks between the spreadsheet formats used at Northumbria:

| Tool | What it does |
|------|-------------|
| [Gradebook Merger](#gradebook-merger) | Copies marks from your local marking sheet into a Blackboard Gradebook export |
| [MCRF Populator](#mcrf-populator) | Copies marks from your local marking sheet into a blank MCRF template |

Student IDs are normalised automatically to handle format differences (e.g. `w12345678`,
`12345678`, `W12345678/1` are all treated as the same student).

---

## Gradebook Merger

Use this when you have marked in a local Excel file and need to upload marks to Blackboard.

### What you need

- **Your marking sheet** — any Excel, CSV, or TSV file with a student ID column and a mark column.
  Can be a Blackboard Gradebook export (UTF-16 TSV), MCRF `.xls`, or plain `.xlsx` / `.csv`.
- **The Blackboard Gradebook export** — downloaded from Blackboard Grade Centre
  ("Work Offline → Download").

### Steps

1. Go to **Marking Converters → Gradebook Merger**.
2. Upload both files and click **Upload**.
3. On the **Match** page:
    - Select the **Student ID column** from your marking sheet.
    - Select the **Student ID column** from the Blackboard file.
    - Map one or more **mark columns**: choose the column in your marking sheet and the
      corresponding column in the Blackboard file.
    - Click **Download Merged Gradebook**.
4. The merged file is downloaded as `Merged_Blackboard_Gradebook.csv`.
5. Upload this CSV back to Blackboard via **Work Offline → Upload**.

> If zero students are matched, check that the same ID format is used in both files.
> The error message shows a sample of normalised IDs from each file to help you diagnose the mismatch.

---

## MCRF Populator

Use this when you have marked in a local Excel file and need to populate the institution MCRF template.

### What you need

- **Your marking sheet** — any Excel, CSV, or TSV file with a student ID column and mark columns.
- **The blank MCRF template** — the institution `.xls` file with student IDs already entered
  (e.g. downloaded from the registry or student record system).

### Steps

1. Go to **Marking Converters → MCRF Populator**.
2. Upload both files and click **Upload**.
3. On the **Match** page:
    - Select the **Student ID column** from your marking sheet.
    - Select the **Student ID column** from the MCRF template.
    - Map one or more **mark columns**: choose the column in your marking sheet and the
      corresponding column in the MCRF template.  
      (Only columns containing "mark" in their header are shown for the MCRF side.)
    - Click **Download Populated MCRF**.
4. The populated file is downloaded as `<original_filename>_Populated.xls` (or `.xlsx`).

> The original MCRF formatting and cell styles are preserved exactly — the tool writes
> only to the mark cells you map.

---

## Supported file formats

| Format | Notes |
|--------|-------|
| `.xlsx` | Standard Excel workbook |
| `.xls` | Legacy Excel / MCRF format (read with `xlrd`) |
| `.csv` | Comma-separated, UTF-8 |
| `.xls` (Blackboard export) | UTF-16 tab-separated text saved with `.xls` extension — detected automatically |

---

## Tips

- The student ID match is case-insensitive and strips common prefixes/suffixes (`w`, `/1`).
- If your marking sheet has separate first and last name columns, you can still use it —
  the ID column is what drives the match, not the name.
- Always review the downloaded file before submitting to ensure marks look correct.
