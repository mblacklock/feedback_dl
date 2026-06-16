# Assessment Feedback

Generate personalised, per-student feedback sheets from a marks spreadsheet. Each sheet
is a self-contained HTML file with no external dependencies — safe to email directly to students.

---

## What you need

- An Excel spreadsheet (`.xlsx`) containing one row per student with columns for:
    - Student name (or separate first / last name columns)
    - Student ID
    - One or more mark or rubric columns (e.g. `Design /30`, `Implementation /40`)
    - Optionally: matching feedback comment columns, a pre-calculated overall/total column,
      and a group/team column

---

## Step-by-step

### Step 1 — Upload

1. Go to **Assessment Feedback**.
2. Drag and drop your marks spreadheet in the box or click to browse your local files.
3. Click **Analyse Spreadsheet**.
4. The app reads the file entirely in memory — nothing is saved to disk.

The app automatically detects:

- The **student name** column (looks for "name", "student", "forename", "surname" etc.)
- The **student ID** column (looks for "id", "number", "code")
- Any **overall / total** column
- Mark columns (numeric) and rubric columns (grade-string values such as "High 2:1")
- Matching **comment** columns paired to each mark column
- A **group / team** column if present
- The **denominator** (max marks) from the column header (e.g. `/30`) or from the data maximum

If no grading columns are detected the upload is rejected with an error message.

---

### Step 2 — Confirm mappings

The Mappings page shows the auto-detected column assignments and allows you to change them if needed. 

| Field | Description |
|-------|-------------|
| **Student name** | Column used for the student's display name |
| **Student ID** | Column used for the student identifier |
| **Overall mark** | Pre-calculated total column, if present, or select **[Sum categories dynamically]** to calculate total from all numeric and rubric columns |
| **Group** | Group / team label column, if present |
| **Degree level** | Honours (BEng/BSc) or Master's level (MEng/MSc) — affects grade band boundaries |
| **Module details** | Module code, title, assessment component & title, academic year |

For each detected mark / rubric column you can:

- Edit the **column title** (denominators are stripped automatically)
- Change the **max marks** (denominator)
- Change the **column type**: Numeric, Rubric, Information, or Feedback only
- Set a matching **comments column**, if present
- Toggle **exclude from radar chart**
- Remove the column entirely
- Add extra columns using **Add Undetected Column**

> **Rubric columns** contain grade strings such as "Mid 2:1" or "High 1st" instead of numbers.
> The app detects these automatically and maps them to numeric marks using the UK grade band scale.
> You can edit the rubric mappings to match your own custom rubric.

Click **Build Feedback Sheet Layout** when you are happy with the settings.

---

### Step 3 — Configure layout

A drag-and-drop WYSIWYG editor lets you arrange the blocks that appear on each feedback sheet. A preview for each student can be seen by updating the dropdown box.

| Block | Contents |
|-------|----------|
| **Assessment & Student details** | Name, ID, module, assessment, academic year |
| **Marks table** | Per-criterion mark, max marks, grade band label |
| **Radar chart** | Student vs cohort average per criterion |
| **Cohort histogram** | Grade distribution with student's mark highlighted |
| **Feedback comments** | Text from matched comment columns |
| **General feedback comments** | Free text editor to add whole-class comments |

Each block can be set to **full width** or **half width**, enabled or disabled, and reordered
by dragging. When a block is selectded to **half width** it can be toggled to be on its own row or next to another half-width block.

A live preview updates as you make changes. 

Within the **Marks table** preview block, you can also customize row layouts:
- **Reorder criteria rows**: Drag and drop any row in the Breakdown of Marks table preview to rearrange the order in which criteria appear on the final sheets.
- **Highlight rows**: Hover over a row and click the **Highlight** badge to toggle it as a section header (bold, light background, hiding mark/comment fields).
- **Add divider lines**: Hover over the boundary between rows and click **━ Add Divider** to insert a solid gray separator line. Hover and click **✕ Remove Divider** to remove it.

Click **Generate Student Feedback Sheets** to produce the output.

---

### Output

- A **ZIP file** containing one HTML file per student, named `<student_id>_<student_name>.html`
- A pre-populated **email template** macro workbook (`.xlsm`). This can be used alongside MS Outlook to programmatically send emails to students with the relevant HTML feedback file attached. It does not require access to your account information to send emails. It uses the an open MS Outlook instance to send the emails.

Each HTML file is fully self-contained — all CSS, SVG charts, and data are embedded inline.

---

## Tips

- If the wrong column is detected as the student name, correct it on the mapping page before proceeding.
- Columns whose headers contain `/20`, `(30)`, or a trailing integer have their denominator
  inferred automatically. If no denominator is found, the app checks the data maximum. 
  The maximum mark for a category can be edited in the mapping page.
- Rubric columns (grade strings) must have ≥ 70 % of values matching recognised UK grade strings
  to be detected automatically.
- For Master's-level modules, select **MEng/MSc** as the degree level — the pass boundary
  shifts to 50 % and Distinction / Merit / Pass grade labels will also be auto-detected along with the standard 1st / 2:1 etc. rubric strings.
- The radar chart excludes "Information" and "Feedback only" columns by default. You may exclude other categories on the mapping page.
