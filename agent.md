# Feedback Generator — Agent Context

## Project Purpose
A Django web app for university academics at Northumbria University. It generates personalised student feedback sheets from marks spreadsheets, and cohort-level analytics reports for module tutors. Colleagues will use this too — robustness and flexibility are priorities.

## Critical Constraints
- **No student data may be persisted to a database** — GDPR. All student data lives in Django sessions only (using keys like `uploaded_data`, `mappings`, and `headers`) and is discarded after the output is served. This is non-negotiable.
- **Development environment**: Windows (VS Code-based) running locally at `http://127.0.0.1:8000`. **Deployment**: PythonAnywhere.
- **Output**: self-contained HTML files, not PDFs. All CSS/charts are embedded — the file a student receives has no external dependencies.
- **VS Code formatter strips whitespace from Django template tags** — `formatOnSave` is disabled for `django-html` files. Do not re-enable it.

## App Structure

```
feedback_project/
  assessment_feedback/   # Per-student feedback sheets from a marks spreadsheet
  module_summary/        # Per-student module summary from two assessment spreadsheets
  cohort_report/         # Tutor-facing cohort analytics report from an MCRF spreadsheet
  core/                  # Shared utilities — charts, band mapping, session helpers, MCRF parser
  comments_generator/    # Comments generator from a pool
  marking_converters/    # Converter between gradebook export files and MCRF-compatible format
  marking_sheet_builder/ # Create a marking spreadsheet from a template
  rubric_generator/      # Rubric generator
```

### `assessment_feedback`
- Upload a marks spreadsheet → column mapping confirmation → configure layout → generate zip of HTML files per student
- Each HTML contains: student details, criterion marks + UK grade band labels, feedback comments, radar chart, cohort histogram
- Layout is configurable (block order, full/half width, enable/disable) via a WYSIWYG drag-and-drop editor
- Category visual styles are configurable directly in the preview table (highlighting a row to make it a section header, or inserting a solid gray visual divider line below a row)
- Also generates a pre-populated `.xlsm` email file (template at `assessment_feedback/resources/email_template.xlsm`) using `openpyxl` with `keep_vba=True` — never saved to disk

### `module_summary`
- Upload two assessment spreadsheets in one session → per-student summary HTML
- Uses the MCRF parser from `core`

### `cohort_report`
- Upload an MCRF spreadsheet → column mapping → single cohort HTML report (renders in browser + downloadable)
- Shows per-component and overall module: histogram, mean, median, std dev, max, n, % 1st, % 2:1 and above, % 2:2 and above, % fail
- No per-student data in output — aggregated only

### `core`
- `charts.py` — Matplotlib SVG chart generation. Three functions:
  - `generate_radar_chart(categories, student_pct, average_pct, pass_mark=40)` — polygon grid radar, green student, blue average, red dashed pass mark ring
  - `generate_cohort_histogram(scores, student_score, degree_level=None)` — percentage-based, 10% bins, coloured by UK grade band, dashed student mark line
  - `generate_module_comparison_chart(labels, student_pct, average_pct)` — grouped bar chart
- `mcrf_parser.py` — parses MCRF `.xls` spreadsheets (institution format). Used by both `module_summary` and `cohort_report`
- UK grade band mapping — default honours scale, overridable per upload. M-level pass boundary is 50% not 40%

## Spreadsheet Handling
- All parsing in-memory with `openpyxl` — files never written to disk
- MCRF files are legacy `.xls` format — use `xlrd` engine
- Gradebook export files are UTF-16 TSV saved with `.xls` extension — read with `encoding='utf-16'`
- Column role auto-detection with a confirmation/correction UI step for ambiguous cases
- Denominators inferred from column headers (e.g. `/20`) or data max; prompted in UI if neither works
- Assessment weights inferred from headers or prompted in UI if not found

## Shared Template Assets
- `feedback_blocks.css` — shared CSS for `_feedback_block.html` partial. Linked in both `feedback_sheet.html` and `configure_layout.html` so the WYSIWYG preview matches the generated output
- All feedback sheet styling uses system fonts (Georgia, Helvetica Neue, Arial) — no web font imports
- Colour palette: navy `#1a1a2e`, gold `#c8a951`, grade band colours match histogram bars

## Testing
- TDD following *Obey the Testing Goat* methodology
- Functional tests (Selenium using Chrome/ChromeDriver) written first, then unit tests
- Test fixtures: `dummy_grades.xlsx`, `gc_2025SEM1_KB5034BNN01_dummy.xls`, `KB5034_blank_MCRF_25-26_dummy.xls` (all anonymised)

## Requirements
- Split into two files under `requirements/`:
  - `requirements/base.txt` — production dependencies only (no Selenium)
  - `requirements/dev.txt` — includes `-r base.txt` plus Selenium, MkDocs, and their transitive deps
- `requirements.txt` at the root redirects to `base.txt` for backwards compatibility — do not add packages there directly
- Local dev install: `pip install -r requirements/dev.txt`
- Production install (deploy script): `pip install -r requirements/base.txt`

## Documentation (MkDocs)
- User guides live in `docs/` as Markdown files, one per app, with a home page at `docs/index.md`
- Config: `mkdocs.yml` at the project root using the **Material** theme
- Built output goes to `site/` (git-ignored) — rebuild with `.venv\Scripts\python.exe -m mkdocs build`
- Django redirects `/docs/` to the GitHub Pages site via `RedirectView` (configured in `core/urls.py`)
  - `path("docs/", ...)` → redirects to `https://mblacklock.github.io/feedback_dl/`
  - `path("docs/<path:path>", ...)` → redirects sub-pages to their GitHub Pages equivalents
- Live preview (separate from Django): `.venv\Scripts\python.exe -m mkdocs serve` on port 8001
- When updating docs: edit the `.md` file in `docs/`, then run `mkdocs gh-deploy` to publish to GitHub Pages
- Changelog: edit `CHANGELOG.md` at the project root only. A hook (`docs/hooks.py`) automatically copies it to `docs/changelog.md` during MkDocs builds. The generated `docs/changelog.md` file is git-ignored.
- Docs are deployed to **GitHub Pages**, not served by Django on PythonAnywhere — `mkdocs gh-deploy` from local machine
- Deploy script (`deploy.sh`) does **not** run `mkdocs build` — docs are a separate concern
  - Runs: `git pull` → `pip install` → `migrate` → `collectstatic` → `touch` wsgi file to reload

## Rules
- Dedicated files for CSS and JS
- Keep it DRY across each app and the project
- Suggest a git commit message for the user at the end of each task in the full format "git commit -m ''" (do NOT run modifying git commands on the terminal; read-only commands like git status/diff are okay)
- Changelog updates: When introducing new user-facing features or tool updates, add them to `CHANGELOG.md` at the project root under the latest release. Keep entries high-level and focused on feature updates for colleagues (avoid technical developer details like dependencies, scripting, or setup). Never edit `docs/changelog.md` directly.