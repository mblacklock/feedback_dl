# TODO

## Production Safety (Skipped For Now)

- [ ] Move `SECRET_KEY` to an environment variable in production settings.
- [ ] Rotate the deployed production secret key after removing the committed one.
- [ ] Add basic upload limits or row-count guardrails for large spreadsheets.
- [ ] Review whether parsed spreadsheet data should be stored in Django sessions for large cohorts.

## Documentation 

- [ ] Read through and check 

## Future Enhancements

 - [ ] Rubric generator - Review app
 - [ ] Comment generator - Allow option to upload pool comments.  Allow option to create categories 
 - [x] Move row in layout
 - [x] Half category on own row

 ## New Feature

Task: Create programme_analytics Django App
Overview
A programme-level analytics app that aggregates data across multiple modules to reveal patterns invisible at module level. Stateless for now — no student database. Designed to extend to persistence later without rearchitecting.

Create the App
bash
python manage.py startapp programme_analytics
Register in INSTALLED_APPS and project urls.py at /programme-analytics/.

Data Input
Accept multiple MCRF .xls files (batch upload via drag-and-drop or file picker), a single .zip containing MCRF files, or a mix. Handle all cases on the backend
Same MCRF format as module_summary and cohort_report — use core.mcrf_parser.py
One file per module
User Flow
Upload files → module mapping confirmation → view analytics dashboard → download snapshot

Module Mapping
After upload, show a confirmation page listing each detected module with:

Module code (parsed from filename or spreadsheet)
Auto-detected level — inferred from the first digit of the numeric part of the module code (e.g. KB4001 → level 4, KB5034 → level 5). Handles variable subject prefixes (KB, EE, ME etc.)
Editable level field in case auto-detection is wrong
Programme and year fields (manual entry for now)
Auto-detection rule: strip non-numeric prefix, take first digit of remainder.

Features — Build in This Order
Phase 1 — Module aggregates (no student IDs)

Per-module: mean, median, std dev, grade distribution (% 1st, 2:1, 2:2, 3rd, fail)
Module comparison — means and distributions side by side
Outlier module flags — reuse the same thresholds as cohort_report (check cohort_report for defined values)
Phase 2 — Student trajectories (anonymised)

Hash student IDs at upload using SHA-256 with a server-side salt: hashlib.sha256((ANALYTICS_SALT + student_id).encode()).hexdigest()
Store only the hash — never the raw student ID
ANALYTICS_SALT stored in .env and Django settings, never committed to git
Cross-module performance per anonymised student
Flag underperformance and sudden drops relative to that student's own average
Phase 3 — Year-on-year trends

After processing a cohort, user downloads a snapshot JSON containing module-level aggregates only (no student data)
On future visits, user re-uploads previous snapshots alongside new data
App compares current cohort against historical snapshots
Snapshot format: { programme, year, modules: [{ code, level, mean, std_dev, grade_dist, n }] }
Future Fields
Include programme and year identifiers in all data structures from the start, even if not used in Phase 1, to avoid rearchitecting later.

Key Constraints
Session-based — no student data persisted
Anonymised IDs (hashed) for trajectory features
Aggregates only in snapshots — GDPR-safe
Consistent styling with existing apps
Reuse core.charts.generate_cohort_histogram for distributions
Reuse core.mcrf_parser for MCRF parsing
Add card to landing page linking to /programme-analytics/