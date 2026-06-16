# Cohort Summary Report

Generate a **tutor-facing** cohort analytics report from a completed MCRF spreadsheet.
The report shows aggregated statistics and histograms for each assessment component and
the overall module — **no per-student data appears in the output**.

---

## What you need

- A completed **MCRF** (Module Marks Record Form) `.xls` spreadsheet for the module.

---

## Step-by-step

### Step 1 — Upload

1. Go to **Cohort Summary Report → Upload**.
2. Drag and drop your MCRF spreadheet in the box or click to browse your local files.
3. Click **Analyse Cohort Data**.
4. The app reads the file entirely in memory — nothing is saved to disk.

The app automatically detects:

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

Click **Generate Cohort Report**.

---

### Step 3 — View and download report

The report is rendered directly in the browser, showing:

#### Per component
- **Aggregated statistics**: Mean, median, standard deviation, maximum, and cohort size.
- **UK grade bands**: Proportion of students scoring 1st (≥ 70%), 2:1 and above (≥ 60%), and Fail (below the pass threshold).
- **Cohort histogram**: Chart with UK grade band colours and 10% bins.

#### Overall module
The same statistics and histogram calculated from each student's **weighted final mark**
(sum of component marks multiplied by their weights).

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
