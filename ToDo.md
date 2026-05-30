# TODO

## Production Safety (Skipped For Now)

- [ ] Move `SECRET_KEY` to an environment variable in production settings.
- [ ] Rotate the deployed production secret key after removing the committed one.
- [ ] Add basic upload limits or row-count guardrails for large spreadsheets.
- [ ] Review whether parsed spreadsheet data should be stored in Django sessions for large cohorts.

## Future Enhancements

- [x] Ability to have non-mark categories, e.g. for performance data.
- [x] General assessment feedback/freeform comments.
- [x] Create a marking spreadsheet from a template.
- [ ] Add a changelog file.
