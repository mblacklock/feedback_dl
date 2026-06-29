# Project To-Do List

## 🔒 Production Safety
- [ ] Move `SECRET_KEY` to an environment variable in production settings.
- [ ] Rotate the deployed production secret key after removing the committed one.
- [ ] Add basic upload limits or row-count guardrails for large spreadsheets.
- [ ] Review whether parsed spreadsheet data should be stored in Django sessions for large cohorts.

## 📝 Documentation
- [ ] Read through and check all generated docs.

## 🚀 Future Enhancements
- [ ] **Rubric Generator**: Review overall application.
- [ ] **Comment Generator**: 
  - [ ] Allow option to upload pool comments.
  - [ ] Allow option to create categories.
- [ ] **Testing**: Migrate existing unit and functional tests to native pytest style (converting classes to functions, and using native fixtures and assertions).
- [x] Move row in layout.
- [x] Half category on own row.


---

## 🔄 Feature: longitudinal_analytics Django App [COMPLETED]

A tutor-facing app that tracks cohort trajectories across years and modules, identifying correlations, progression patterns, and entry route effects. Students are linked by ID within the session only — output is always aggregate, no individual records persisted.

### ⚙️ App Setup & Integration
- [x] Create app: `python manage.py startapp longitudinal_analytics`
- [x] Register `longitudinal_analytics` in `INSTALLED_APPS` and core `urls.py` at `/longitudinal-analytics/`
- [x] Add card to landing page linking to `/longitudinal-analytics/`

### 📥 Data Input & Mapping Confirmation
- [x] Accept batch upload of multiple MCRF files (drag-and-drop, zip, or mix)
- [x] Use `core.mcrf_parser` to parse student ID (session-only), module code, year, component marks, and overall mark
- [x] Show module/year mapping confirmation step (auto-detect module code & level, allow editing level/year per file)

### 📊 Analysis Dashboard
- [x] **Correlation Matrix**:
  - [x] Calculate pairwise correlation between module marks across the dataset
  - [x] Render correlation heatmap (modules as rows/columns, colored by correlation coefficient) using Chart.js
  - [x] Support expanding scatter plot of two modules on clicking a cell with configurable/non-persisting non-submission threshold highlighting
- [x] **Cohort Progression**:
  - [x] Show mean mark per level (3, 4, 5, 6, 7) to track cohort movement
  - [x] Show distribution of mark changes between levels (improving, declining, stable)
  - [x] Identify level transitions where significant drops occur
- [x] **Entry Route Analysis**:
  - [x] Compare outcomes for students with Level 3 records vs direct entrants (no Level 3 records)
  - [x] Infer entry route from presence/absence of Level 3 module marks in the dataset
- [x] **Predictive Indicators**:
  - [x] Identify early modules (Level 3/4) that strongly correlate with final year (Level 6/7) outcomes
  - [x] Flag module combinations where poor performance is a strong predictor of later difficulty

### 🔒 Key Constraints & Security
- [x] Session-based tracking: student IDs used as join keys within session only, never persisted
- [x] Output is always aggregate: no individual student records shown in the dashboard
- [x] Reuse Chart.js for all visualisations
- [x] Consistent styling with existing apps