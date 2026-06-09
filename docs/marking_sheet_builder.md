# Marking Sheet Builder

Generate a blank, pre-formatted Excel marking spreadsheet template
(`.xlsx`) ready to fill in during marking.

---

## What it does

The builder creates a workbook with:

- A **Marking Sheet** tab with header rows, student ID / name columns, your chosen
  marking columns, and auto-calculated **Mark** and **%** columns.
- A hidden **Rubric Boundaries** tab that drives Excel dropdown validation for rubric columns.
- Cell borders, column widths, and frozen header rows applied automatically.

---

## Configuration

### Basic settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Student name mode** | *Full name* (single column) or *Split* (separate Last Name / First Name columns) | Full name |
| **Degree level** | Honours (BEng/BSc) or Master's level (MEng/MSc) — affects rubric grade band boundaries | BEng/BSc |
| **Number of student rows** | How many blank data rows to include (1–500) | 100 |
| **Total max marks** | The maximum mark for the whole assessment (e.g. 100) | 100 |

### Column types

Add one or more marking columns. Each column has a **title** and, for numeric and rubric
columns, a **max marks** value.

| Type | Description |
|------|-------------|
| **Numeric** | A plain number entry. Excel validates that the entered value is between 0 and max marks. |
| **Rubric** | A dropdown cell populated from UK grade band strings (e.g. "High 2:1"). Excel looks up the corresponding numeric mark automatically. |
| **Information** | A free-text or measurement column (e.g. "Load (N)"). Not included in the mark calculation. |
| **Feedback** | A text column for written feedback. Placed at the end of the sheet. Not included in the mark calculation. |

> **Important:** The sum of the max marks of all **Numeric** and **Rubric** columns must equal
> the **Total max marks** setting. The builder will show an error if they do not match.

### Rubric settings

For each **Rubric** column you can choose a **subdivision** level:

| Subdivision | Grade strings available |
|-------------|------------------------|
| **None** | 1st, 2:1, 2:2, 3rd, Fail |
| **High / Low** | High 1st, Low 1st, High 2:1, Low 2:1, … |
| **High / Mid / Low** | High 1st, Mid 1st, Low 1st, High 2:1, Mid 2:1, Low 2:1, … |

You can also override the default mark for any grade band using the **Custom marks** fields
that appear when you expand a rubric column's settings.

---

## Downloading

Click **Build & Download** to generate and download `marking_sheet_template.xlsx`.

Open the file in Excel. The **Marking Sheet** tab is ready to use:

- Type student IDs and names in the first columns.
- Enter numeric marks directly, or choose a rubric grade from the dropdown.
- The **Mark** and **%** columns calculate automatically.

---

## Tips

- Use **Rubric** columns when your marking criteria use grade descriptors rather than
  raw numbers. The hidden lookup table converts the selected grade string to a numeric mark.
- Add a **Feedback** column for each criterion that has written comments —
  these will be picked up automatically when you later upload the sheet to
  [Assessment Feedback](assessment_feedback.md) (the column title just needs to contain
  the word "feedback" or "comment").
- Set the number of rows to match your cohort size to keep the file tidy.
