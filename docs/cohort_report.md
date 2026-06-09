# Cohort Report

Generate a **tutor-facing** cohort analytics report from a completed MCRF spreadsheet.
The report shows aggregated statistics and histograms for each assessment component and
the overall module — **no per-student data appears in the output**.

---

## What you need

- A completed **MCRF** (Module Marks Record Form) `.xls` spreadsheet for the module.

---

## Step-by-step

### Step 1 — Upload

1. Go to **Cohort Report → Upload**.
2. Select your MCRF `.xls` file and click **Upload**.
3. The file is parsed in memory — nothing is written to disk.

The app automatically detects:

- Student name and ID columns (used for internal processing only, never shown in output)
- Assessment **component mark** columns (headers containing "mark", excluding totals and averages)
- **Module code**, **module title**, **year**, **period**, and **occurrence** from the MCRF header
- **Component weights** from column headers (e.g. `CW1 40%`); split evenly if not found

---

### Step 2 — Confirm mappings

Review and adjust before generating:

| Field | Description |
|-------|-------------|
| **Module code / title** | Pre-populated from the MCRF; editable |
| **Year / period / occurrence** | Pre-populated from the MCRF; editable |
| **Degree level** | BEng/BSc or MEng/MSc — sets the fail threshold (40 % or 50 %) |
| **Component weights** | Must sum to exactly 100 % |

Click **Confirm & Continue**.

---

### Step 3 — View and download report

The report is rendered directly in the browser, showing:

#### Per component
| Statistic | Description |
|-----------|-------------|
| Mean | Average percentage |
| Median | Middle value |
| Std dev | Standard deviation |
| Max | Highest percentage |
| n | Number of students |
| % 1st | Proportion scoring ≥ 70 % |
| % 2:1 and above | Proportion scoring ≥ 60 % |
| % 2:2 and above | Proportion scoring ≥ 50 % |
| % Fail | Proportion below the pass threshold |

Each component also has a **cohort histogram** with UK grade band colours and 10 % bins.

#### Overall module
The same statistics and histogram calculated from each student's **weighted final mark**
(sum of component percentages multiplied by their weights).

### Downloading

Click **Download Report** to save a single self-contained HTML file with all charts and
statistics embedded inline — no internet connection required to view it.

The filename is `cohort_report_<module_code>.html`.

---

## Tips

- For Master's-level modules select **MEng/MSc** — the fail threshold changes to 50 %
  and the grade label in the histogram changes accordingly.
- The report contains **no individual student names or IDs**. It is safe to share with
  external examiners or quality panels.
- If component weights do not sum to 100 %, the confirm page will show an error and
  prevent generation.
