# Module Summary

Generate a per-student module summary sheet from a completed MCRF spreadsheet.
Each summary shows the student's marks across all assessment components, their weighted
final percentage, overall grade, and a cohort histogram.

---

## What you need

- A completed **MCRF** (Module Marks Record Form) `.xls` spreadsheet for the module.
  The app uses the institution MCRF format and reads it with the legacy `xlrd` engine.

---

## Step-by-step

### Step 1 — Upload

1. Go to **Module Summary → Upload**.
2. Select your MCRF `.xls` file and click **Upload**.
3. The file is parsed entirely in memory — nothing is written to disk.

The app automatically detects:

- The student **name** and **ID** columns
- Assessment **component mark** columns (any column whose header contains "mark",
  excluding totals, averages, and overall columns)
- The **module code** and **module title** from the MCRF header rows
- **Component weights** from column headers if present (e.g. `CW1 40%`);
  if not found, weights are split evenly across components

---

### Step 2 — Confirm mappings

Review and adjust the auto-detected settings:

| Field | Description |
|-------|-------------|
| **Student name** | Column used for the student's display name |
| **Student ID** | Column used for the student identifier |
| **Module code / title** | Pre-populated from the MCRF header; editable |
| **Component weights** | Must sum to exactly 100 % before you can proceed |

Each component row shows its column name and an editable weight field.

> Component weights must add up to **100 %** exactly. The app will display an error if they do not.

Click **Confirm & Continue** when you are happy.

---

### Step 3 — Configure layout

A drag-and-drop WYSIWYG layout editor (identical to the one in Assessment Feedback)
lets you arrange the three blocks on each summary sheet:

| Block | Contents |
|-------|----------|
| **Assessment Breakdown Table** | Per-component percentage, weight, and grade |
| **Comparative Visual Chart** | Grouped bar chart: student vs cohort average per component |
| **Weighted Final Score Card** | Final weighted percentage and overall grade band |

Each block can be set to full or half width, enabled or disabled, and reordered.
A live preview lets you switch between students in the cohort.

Click **Generate** to produce the output.

---

### Output

- A **ZIP file** containing one HTML file per student, named
  `module_summary_<student_id>_<student_name>.html`

Each file is fully self-contained with embedded charts and CSS.

---

## Tips

- Marks should be in the 0–100 range for each component (the MCRF format stores them
  as percentages).
- A special rounding rule applies: any percentage whose integer part ends in 9
  (e.g. 39.x %, 59.x %) is rounded up to the next decade (40 %, 60 %) to follow
  module reporting conventions.
- If the MCRF has no explicit weights in its headers, all components are weighted equally.
