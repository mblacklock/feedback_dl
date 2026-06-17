# Programme Analytics App — User Guide

The **Programme Analytics** application enables academic programme leaders to aggregate, compare, and analyse student performance across multiple modules and cohorts. By correlating different module marks, the tool highlights progression trends, assessment component strengths/weaknesses, and student performance anomalies.

---

## 🚀 Getting Started

To access Programme Analytics, navigate to the **Programme Analytics** tool card on the portal home page, or go to `/programme-analytics/`.

### Step 1: Uploading Cohort Spreadsheets
1. Locate the drag-and-drop area on the upload screen.
2. Select or drop multiple **Module Marks Record Form (MCRF)** spreadsheets (`.xlsx` or legacy `.xls` format).
3. Alternatively, you can upload a single `.zip` file containing multiple spreadsheets.
4. Click **Analyse Programme** to begin parsing the files.

---

## 🗺️ Step 2: Confirming Module Definitions & Mapping

After uploading, you will be presented with the **Confirm Programme Mapping** configuration page:

1. **Programme Details**:
   - Provide a **Programme Name** (e.g. *BEng (Hons) Computer Science*).
   - Verify or edit the **Academic Year** (auto-detected from the files, e.g. *2025/26*).

2. **Module Table definitions**:
   - **Module Code & Title**: Editable fields initialized with values parsed from the spreadsheets (or file names).
   - **Credits**: Auto-detected from Row 8, Col E in each module's MCRF. You can manually edit the credit values (defaulting to 20 if undetected).
   - **Academic Level**: Auto-detected from module prefix digits (e.g. `EE5034` $\to$ Level 5). Adjust this using the dropdown if needed.

3. **Assessment Component Mapping**:
   - Expand the sub-panels to view detected marking columns.
   - Use the category dropdowns to map columns to normalised assessment categories:
     - `Individual CW` (Coursework)
     - `Exam` (Examinations, tests, quizzes)
     - `Presentation` (Vivas, pitches, oral talks)
     - `Group CW` (Team projects)
     - `Portfolio` (Compilation of works)

Click **Confirm and View Dashboard** to process the cohort.

---

## 📊 Step 3: Interactive Dashboard

The dashboard organizes analytics into four key tabs:

### 1. 📋 Module Summary Table
- **Main View**: A comprehensive table listing module codes, titles, levels, cohort sizes, mean marks, medians, standard deviations, and percentages for **1st Class**, **2:1 & above**, and **Fail** rates.
- **Status Flags**: High-risk outliers are marked with red/warning flags:
  - 🚩 **High Fail**: Exceeds a 20% fail rate.
  - 🚩 **High 1st**: Exceeds a 20% first-class rate.
  - Left completely blank if performance is normal.
- **Interactive Inline Reports**: Click any module row to expand an inline report. This reveals the module overall performance card (averages, min/max) and the component breakdown statistics (histograms and component details).
- **Filtering & Search**:
  - **Level Filter**: Filter modules by Levels 4, 5, 6, or 7.
  - **Status Filter**: Filter by Warning Flags, High Fail, or High 1st.
  - **Search**: Dynamically search by module code or title.

### 2. 📈 Normalised Overlay
- Displays a Matplotlib-generated line chart overlaying grade distributions for all modules in this cohort.
- **Cohort Normalisation**: The frequency is normalised to the percentage of each module's cohort size rather than raw counts, ensuring fair comparisons between modules of differing sizes.
- **Line Hover Tooltips**: Hover over data points or any part of the series lines to view exact band percentages, module codes, and names.

### 3. 🔥 Component Heatmap
- A grid showing modules as rows and the five normalised assessment categories as columns.
- Cells display average marks color-coded by **UK Grade Bands** (with pass mark adjustments for academic levels: 40% UG, 50% PG):
  - 🟢 **1st Class** ($\ge 70\%$)
  - 🔵 **2:1 Class** ($60\% - 69\%$)
  - 🟣 **2:2 Class** ($50\% - 59\%$)
  - 🟡 **3rd Class/Pass** ($40\% - 49\%$, UG only)
  - 🔴 **Fail** ($< 40\%$ UG, $< 50\%$ PG)
- Displays module code and title on a single line for clean visual alignment.

### 4. 🎓 Level Benchmarking
- **Grouped Grade Band Chart**: A Matplotlib bar chart showing all five grade bands (Fail, 3rd, 2:2, 2:1, 1st) side-by-side, grouped by level.
- **Credit-Weighted Student Trajectory Aggregates**:
  - Automatically identifies unique student records across all modules at each level.
  - Calculates a single credit-weighted average mark for each unique student at that level:
    $$M_{student\_level} = \frac{\sum (Mark_{module} \times Credit_{module})}{\sum Credit_{module}}$$
  - Summarizes cohort size, mean, and grade band rates (`% 1st`, `% 2:1 or above`, `% Fail`) based on these student-level averages rather than raw module scores.

---

## 🔒 GDPR Compliance & Security

To strictly comply with data protection regulations (including GDPR), the application enforces the following security boundaries:
- **No PII Storage**: Raw Student IDs, names, or usernames are **never** stored in database tables, session caches, or exported files.
- **Anonymised Hashing**: Student IDs are extracted during the initial parsing phase, normalised (whitespaces stripped and lowercased), and hashed immediately using SHA-256 with a secure server-side salt:
  $$\text{hash} = \text{SHA-256}(\text{ANALYTICS\_SALT} + \text{student\_id})$$
- Only the hashed IDs are cached in the session to align student marks across modules.

---

## 💾 JSON Snapshot Export

Click the **Download Snapshot JSON** button in the header block to download a stateless, anonymised archive of the cohort's performance.

### Snapshot Structure
```json
{
    "programme": "BEng (Hons) Computer Science",
    "year": "2025/26",
    "modules": [
        {
            "code": "COMP5034",
            "title": "Object Oriented Programming",
            "level": 5,
            "credits": 20,
            "mean": 53.33,
            "std_dev": 20.5,
            "grade_dist": {
                "pct_1st": 33.3,
                "pct_21_above": 33.3,
                "pct_fail": 33.3
            },
            "score_bins": {
                "absent": 0,
                "bins": [0, 0, 0, 1, 0, 1, 0, 0, 1, 0]
            },
            "n": 3
        }
    ]
}
```
*Note: The snapshot contains only module-level aggregates and contains no student data.*
