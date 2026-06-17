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
- [x] Move row in layout.
- [x] Half category on own row.

---

## 📊 Feature: Programme Analytics Django App

A programme-level analytics app that aggregates data across multiple modules to reveal patterns invisible at the module level. Designed to be stateless (using Django sessions) and easily extendable to a persistent database later.

### ⚙️ App Setup & Integration
- [x] Create app: `python manage.py startapp programme_analytics`
- [x] Register `programme_analytics` in `INSTALLED_APPS` and core `urls.py` at `/programme-analytics/`
- [x] Add card to landing page linking to `/programme-analytics/`

### 📥 Data Input & Parsing
- [x] Accept multiple MCRF `.xls`/`.xlsx` files, a `.zip` archive, or a mix of both in the backend
- [x] Parse uploaded files in memory using `core.mcrf_parser.py` (one file per module)

### 🗺️ Module Mapping & Confirmation
- [x] Show confirmation page listing each detected module:
  - [x] Display module code and source filename
  - [x] Auto-detect academic level from code prefix (e.g. KB4001 → Level 4, EE5034 → Level 5)
  - [x] Provide editable level field for corrections
  - [x] Provide Programme Name and Academic Year fields (saved in session)

### 📈 Phase 1: Module Aggregates (Stateless)
- [x] Compute per-module statistics: mean, median, std dev, cohort size
- [x] Compute per-module grade distribution (% 1st, 2:1, 2:2, 3rd, fail)
- [x] Side-by-side module comparison chart (mean marks & grade bands) using Matplotlib SVG rendering
- [x] Outlier module flags (High Fail rate >20%, High 1st Class rate >20%) matching `cohort_report`
- [x] Transition static histogram list to interactive inline report views (toggled via row click)
- [x] DRY template partial refactoring (`_overall_performance_card.html`, `_components_breakdown_partial.html`)
- [x] Interactive mouseover SVG tooltips using post-processed Matplotlib links

### 🔄 Phase 2: Student Trajectories (Anonymised)
- [x] Hash student IDs at upload using SHA-256 with a server-side salt:
  - `hashlib.sha256((ANALYTICS_SALT + student_id).encode()).hexdigest()`
- [x] Store only the hashed ID (never raw student IDs or PII) to ensure GDPR compliance
- [x] Store `ANALYTICS_SALT` securely in environment variables/settings
- [ ] Calculate and display cross-module performance per anonymised student
- [ ] Flag student underperformance and sudden drops relative to their own average

### 📅 Phase 3: Year-on-Year Trends
- [x] Downloadable snapshot JSON containing module-level aggregates only (no student data)
  - Snapshot format: `{ programme, year, modules: [{ code, level, mean, std_dev, grade_dist, n }] }`
- [ ] Allow uploading previous snapshots alongside new data to compare current cohort against historical trends
- [x] Include programme and year identifiers in all data structures