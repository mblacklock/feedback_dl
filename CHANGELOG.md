# Changelog

All notable changes to the Feedback Portal tools will be documented here.

## [Unreleased]

### Added
- **Theme Customisation**: Added a database-backed dynamic theme customisation tool allowing users to create, edit, activate, and delete custom branding themes.

## [1.1.0] - 2026-06-11

### Added
- **Assessment Feedback**: Added the ability to highlight category rows and insert visual dividers directly within the interactive live layout editor.
- **Assessment Feedback**: Added interactive drag-and-drop category row reordering in the layout designer, allowing custom order configurations of criteria in the Breakdown of Marks table.

### Fixed
- **Assessment Feedback**: Improved compatibility with a wider range of spreadsheet layouts — column detection and category labels now work correctly regardless of how the spreadsheet is structured.
- **Core (static templates)**: Fixed HTML-escaping of inlined CSS files in templates rendered via custom `{% inline_static %}` tags, restoring correct Google Font loading and resolving the `.half-pair > .half` columns layout styling.
- **Assessment Feedback**: Increased the width of generated feedback sheets and module summaries to 1100px for enhanced readability of side-by-side columns.

## [1.0.0] - 2026-06-09

### Added
- **Online User Guide**: Launched a web-based documentation site hosted on GitHub Pages, easily accessible via the new link in the portal's top navbar.
- **Consistent Design**: Updated the typography and styling globally with Inter and Outfit fonts to make the portal's user interface cohesive across all apps.
- **Rubric Generator**: Create, customize, and manage reusable templates for student assessment rubrics.
- **Blank Marking Sheet Builder**: Automatically generate blank spreadsheet templates tailored to your assessment guidelines.
- **Marking Sheet Converters**: Easily convert gradebook files and populate university Module Marks Record Forms (MCRF).
- **Cohort Summary Report**: Create tutor-facing aggregated analytics dashboards and charts from completed MCRF sheets without displaying student names or IDs.
- **Comments Generator**: Build and manage reusable pools of text comments to streamline grading.
- **Module Summary**: Generate student-facing summaries from MCRF files.
- **Assessment Feedback**: Easily compile individual student feedback sheets using marks spreadsheets.
