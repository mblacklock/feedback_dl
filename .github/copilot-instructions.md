# Copilot Instructions for feedback_dl

## Project Overview
Django 5.2.8 application for creating and managing feedback templates for assessments. Staff can build rubric templates with custom categories and scoring criteria.

## Architecture

### Project Structure
- **`core/`**: Django project configuration (settings, URLs, WSGI/ASGI)
- **`feedback/`**: Main feedback app with models, views, templates, and static files
- **`functional_tests/`**: Selenium-based end-to-end tests using `StaticLiveServerTestCase`
- **`manage.py`**: Django CLI entry point

### Key Models (feedback/models.py)
- **`AssessmentTemplate`**: Stores feedback templates with:
  - `component` (IntegerField, required) - Assessment component number
  - `title`, `module_code`, `assessment_title` (text fields)
  - `categories` (JSONField) - ordered list of category dicts with:
    - Required: `{"label": str, "max": int}`
    - Optional: `"type": "numeric"|"grade"` (default: "numeric")
    - Optional: `"subdivision": "none"|"high_low"|"thirds"` (only for grade types)
    - Optional: `"descriptions": {grade: str}` (grade band descriptions)
  - Custom `clean()` validation: categories required, labels non-blank, max marks 1-1000, component required

### URL Structure
- `/feedback/` - Home page (lists all templates with component, module, assessment)
- `/feedback/template/new/` - Create new template (GET redirects to edit page)
- `/feedback/template/<pk>/` - View template summary
- `/feedback/template/<pk>/edit/` - Edit template (autosave via AJAX)
- `/feedback/template/<pk>/update/` - Update template (AJAX endpoint)
- `/feedback/template/<pk>/delete/` - Delete template (POST only, returns JSON)

### Static Files
- JavaScript in `feedback/static/feedback/js/`:
  - `template_builder.js` - Dynamic form for creating templates
  - `template_editor.js` - Autosave and dynamic editing with grade bands support
- Always use `{% load static %}` and `{% static 'path' %}` in templates

## Development Workflows

### Testing (Critical - This Project Uses TDD!)
**Follow "Obey the Testing Goat" methodology - RED, GREEN, REFACTOR**

## 🚨 MANDATORY TDD WORKFLOW FOR ALL CHANGES 🚨

**When adding ANY new feature, YOU MUST write tests in this EXACT order:**

1. **FUNCTIONAL TEST FIRST** (in `functional_tests/`)
   - Write a user-facing test describing the feature from end-user perspective
   - Use Given-When-Then (GWT) comments
   - Run it to see it FAIL (RED)

2. **UNIT TESTS SECOND** (in `feedback/tests/`)
   - **Model test** (`test_models.py`) - if adding/changing model fields
   - **View test** (`test_views.py`) - if adding/changing views or form handling
   - Run them to see them FAIL (RED)

3. **IMPLEMENTATION THIRD**
   - Write minimal code to make tests pass
   - Models → Migrations → Views → Templates → JavaScript
   - Run tests to see them PASS (GREEN)

4. **REFACTOR IF NEEDED**
   - Clean up code while keeping tests passing

**❌ WRONG ORDER (DON'T DO THIS):**
- ❌ Write model test only, skip FT and view tests
- ❌ Write implementation first, then write tests
- ❌ Write model code, then write model test, then discover you need view tests

**✅ CORRECT ORDER (ALWAYS DO THIS):**
- ✅ Functional Test (fail) → Model Test (fail) → View Test (fail) → Implementation (all pass)

```powershell
# Run all tests (recommended for commits)
python manage.py test --parallel=auto  # 60% faster than serial

# Run specific test types
python manage.py test functional_tests  # Selenium end-to-end tests
python manage.py test feedback.tests    # Unit tests

# Run specific test
python manage.py test feedback.tests.test_views.TemplateBuilderViewTests.test_post_valid_creates_template_and_redirects_to_summary
```

**Test Structure:**
- `feedback/tests/test_models.py` - Model validation and behavior (component, categories, grade bands)
- `feedback/tests/test_views.py` - View logic and form handling (create, edit, update, delete)
- `feedback/tests/test_utils.py` - Utility functions (grade band calculations)
- `functional_tests/test_feedback_flow.py` - Home page, navigation, deletion
- `functional_tests/test_template_builder.py` - Template creation flow
- `functional_tests/test_template_autosave.py` - Autosave functionality
- `functional_tests/test_grade_band_descriptions.py` - Grade bands feature

**Test Conventions:**
- Use **Given-When-Then (GWT)** comments in functional tests for BDD clarity
- Unit tests use Django's `TestCase`, functional tests use `StaticLiveServerTestCase`
- JavaScript behavior is tested via functional tests (no separate JS unit tests for simple interactions)
- ALL new features require: 1 FT + 1+ model test (if model changes) + 1+ view test (if view changes)

### Initial Setup
```powershell
# Create/activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate
python manage.py createsuperuser  # Optional: for admin access
```

### Making Changes (TDD Workflow)
1. Write/run failing test first
2. Implement minimal code to pass
3. Refactor if needed
4. Commit when all tests pass

```powershell
# After model changes
python manage.py makemigrations
python manage.py migrate

# Verify all tests pass before committing
python manage.py test --parallel=auto  # Recommended: 60% faster than serial
```

**Current Test Count:** 45 tests (all passing)

### Running the Server
```powershell
python manage.py runserver
```
**Note:** If template changes don't appear, restart the server (templates are cached)

## Project Conventions

### App Registration
```python
# In core/settings.py
INSTALLED_APPS += [
    'feedback',
]
```

### Form Handling Pattern
- POST data with parallel arrays: `category_label` and `category_max` as lists
- Validate in view, show errors in template via `{% if errors %}` block
- Redirect after successful POST (Post-Redirect-Get pattern)

### Version Management
Dependencies are pinned to exact versions in `requirements.txt` (e.g., `Django==5.2.8`, includes Selenium for tests)

### Git Ignores
Standard Django exclusions: `__pycache__/`, `*.pyc`, `.venv/`, `db.sqlite3`, `.vscode/`

### Logging Configuration
- `django.server` logger set to ERROR level in settings.py
- Suppresses harmless "Broken pipe" warnings from Selenium tests
- Actual errors still displayed

## Important Notes for AI Assistants
- **CRITICAL: Follow TDD order**: FT → Model Test → View Test → Implementation (NOT model test only!)
- **Always write ALL three test types** when adding features:
  1. Functional test (user perspective, Given-When-Then)
  2. Model test (if model changes)
  3. View test (if view/form handling changes)
- **Keep changes small**: One failing test → minimal code → pass → next test
- **Check exit codes**: Tests should exit with code 0 (success)
- **Static files**: After creating/editing static files, may need server restart in development
- **Don't skip view tests**: Model tests alone are insufficient - views need testing too!
