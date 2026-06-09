# Rubric Generator

Create, store, and reuse **assessment rubric templates**. A template defines the marking
criteria for an assessment and can be used to:

- View a formatted **rubric table** ready to paste into an assessment brief.
- Preview an **example student feedback sheet** with randomly generated sample marks.

Templates are saved to the database and persist between sessions.

---

## Concepts

| Term | Description |
|------|-------------|
| **Template** | A named rubric for one assessment component. Stores the module details, max marks, and list of criteria (categories). |
| **Category** | A single marking criterion within the template (e.g. "Code quality", "Report structure"). |
| **Grade band** | A mark range within a category, labelled by UK grade (e.g. "High 2:1 — 21–23 marks"). |
| **Grade band description** | A written descriptor for each grade level within a category, used in the rubric table. |

---

## Creating a template

1. Go to **Rubric Generator**.
2. Click **+ New Template**.
3. You are taken to the **Template Editor**. Changes are saved automatically as you type.

### Template settings

| Field | Description |
|-------|-------------|
| **Template title** | Internal label (e.g. "KB5034 CW1 2025/26") |
| **Module code** | e.g. `KB5034` |
| **Module title** | e.g. "Advanced Software Engineering" |
| **Assessment title** | e.g. "Coursework 1 — Design Report" |
| **Component** | Component number (integer) |
| **Weighting** | Percentage weighting of this component within the module |
| **Max marks** | Total marks available for this assessment (e.g. 100) |
| **Degree level** | Honours or Master's level — affects grade band boundaries |

### Adding categories

Click **+ Add Category** to add a criterion. For each category:

| Field | Description |
|-------|-------------|
| **Label** | Short name for the criterion (e.g. "Design") |
| **Max marks** | Marks available for this criterion |
| **Type** | *Numeric* (plain number) or *Grade* (rubric with grade band descriptors) |
| **Subdivision** | For Grade type: None, High/Low, or High/Mid/Low |

For **Grade** categories, a grade band grid appears showing the calculated mark ranges.
You can:

- Write a **descriptor** for each grade level (what a student at that level would produce).
- Override the default **mark boundary** for any grade band.

> The sum of all category max marks should equal the template's **Max marks**. A warning
> is shown if they do not match, but the template is still saved.

---

## Viewing the rubric table

From the template list or editor, click **View Rubric**.

The rubric table shows each category as a row and each grade band as a column,
with your descriptors in each cell. This is designed to be copied and pasted into
Word or an assessment brief template.

---

## Previewing a feedback sheet

Click **Preview Feedback Sheet** to see how a completed feedback sheet would look for
this template. Sample marks are generated automatically (seeded from the template ID,
so the preview is consistent each time you view it).

This preview uses the same layout as the [Assessment Feedback](assessment_feedback.md) app.

---

## Managing templates

| Action | How |
|--------|-----|
| **Edit** | Click the template name or the edit icon on the home page |
| **Delete** | Click the bin icon on the home page — this is permanent |
| **Duplicate** | Not yet available; create a new template and copy settings manually |

---

## Tips

- Build rubric templates **before** you mark, so that colleagues can use the same grade
  band boundaries consistently.
- The **Marking Sheet Builder** uses the same grade band logic — set the same degree level
  and subdivision in both tools to ensure consistency.
- Grade band descriptors are optional but greatly improve the quality of student feedback
  when used alongside the Assessment Feedback app.
