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
  - `title`, `module_code`, `assessment_title` (text fields)
  - `categories` (JSONField) - ordered list of `{"label": str, "max": int}` dicts
  - Custom `clean()` validation: categories required, labels non-blank, max marks 1-1000

### URL Structure
- `/feedback/` - Home page
- `/feedback/template/new/` - Create new template (form with dynamic JS)
- `/feedback/template/<pk>/` - View template summary

### Static Files
- JavaScript in `feedback/static/feedback/js/` (e.g., `template_builder.js` for dynamic forms)
- Always use `{% load static %}` and `{% static 'path' %}` in templates

## Development Workflows

### Testing (Critical - This Project Uses TDD!)
**Follow "Obey the Testing Goat" methodology - RED, GREEN, REFACTOR**

```powershell
# Run unit tests
python manage.py test feedback.tests

# Run functional tests (Selenium)
python manage.py test functional_tests

# Run specific test
python manage.py test feedback.tests.test_views.TemplateBuilderViewTests.test_post_valid_creates_template_and_redirects_to_summary
```

**Test Structure:**
- `feedback/tests/test_models.py` - Model validation and behavior
- `feedback/tests/test_views.py` - View logic and form handling
- `functional_tests/` - User-facing behavior with Selenium (Given-When-Then style)

**Test Conventions:**
- Use **Given-When-Then (GWT)** comments in functional tests for BDD clarity
- Write failing test FIRST, then implement minimal code to pass
- Unit tests use Django's `TestCase`, functional tests use `StaticLiveServerTestCase`
- JavaScript behavior is tested via functional tests (no separate JS unit tests for simple interactions)

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
python manage.py test
```

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

## Important Notes for AI Assistants
- **Always follow TDD**: Write tests first, implement step-by-step
- **Keep changes small**: One failing test → minimal code → pass → next test
- **Check exit codes**: Tests should exit with code 0 (success)
- **Static files**: After creating/editing static files, may need server restart in development
