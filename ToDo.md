# TODO

## Priority 1: Get Tests Passing

- [x] Update stale redirect assertions from `/confirm/` to the current `/mapping/` routes, or restore `/confirm/` aliases if that is the intended public URL.
- [x] Fix `module_summary.tests` unpacking of `parse_mcrf_workbook()` now that it returns `headers`, `data_rows`, `is_mcrf`, and `module_info`.
- [x] Re-run `python manage.py test assessment_feedback module_summary` and confirm the two main apps are green.
- [ ] Re-run `python manage.py test` and confirm the full suite is green.

## Priority 2: Feedback Accuracy

- [x] Fix M-level rubric band generation so postgraduate reports do not include undergraduate `3rd` bands when fail is below 50%.
- [x] Pass `degree_level` consistently when calculating rubric bands in upload, confirm, API, preview, and final generation paths.
- [x] Add tests for M-level rubric upload, mapping confirmation, preview, and generated HTML output.

## Priority 3: Input Validation

- [ ] Handle invalid or blank max-mark values in `assessment_feedback.confirm_mappings()` without a 500.
- [ ] Handle invalid or blank component weights in `module_summary.confirm_module_mappings()` without a 500.
- [ ] Add user-facing error messages for invalid max marks, invalid weights, and no detected components/categories.
- [ ] Add tests for malformed mapping form submissions.

## Priority 4: Production Safety

- [ ] Move `SECRET_KEY` to an environment variable in production settings.
- [ ] Rotate the deployed production secret key after removing the committed one.
- [ ] Add basic upload limits or row-count guardrails for large spreadsheets.
- [ ] Review whether parsed spreadsheet data should be stored in Django sessions for large cohorts.

## Priority 5: Refactoring And Maintainability

- [ ] Extract duplicated assessment feedback calculation logic shared by preview and ZIP generation.
- [ ] Extract duplicated module summary calculation logic shared by preview and ZIP generation.
- [ ] Remove unused imports such as `Http404` where no longer needed.
- [ ] Check duplication in unit tests and consolidate helper fixtures.

## Future Enhancements

- [ ] Half page with charts on left.
- [ ] Toggle class average on radar chart.
- [ ] Ability to have non-mark categories, e.g. for performance data.
- [ ] General assessment feedback/freeform comments.
- [ ] Create a marking spreadsheet from a template.
- [ ] Import marking sheet from a template or compatible spreadsheet.
- [ ] Generate individual feedback sheets from saved templates.
- [ ] Add a changelog file.
- [ ] Add bulk import/export functionality for templates.
- [ ] Add template duplication feature.
- [ ] Add search/filter functionality on the home page for large numbers of templates.
