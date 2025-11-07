# Copilot Instructions for feedback_dl

## Project Overview
This is a Django 5.2.8 application for managing feedback. The project uses a simple SQLite database and follows Django's standard project structure with a `core` configuration package and a `feedback` app.

## Architecture

### Project Structure
- **`core/`**: Django project configuration (settings, URLs, WSGI/ASGI)
- **`feedback/`**: Main application for feedback functionality (currently minimal setup)
- **`manage.py`**: Django CLI entry point

### Settings Pattern (core/settings.py)
- Custom apps are appended separately using `INSTALLED_APPS += ['feedback']` pattern (line 38)
- Templates use `APP_DIRS = True` for per-app template discovery
- Database: SQLite at project root (`db.sqlite3`)
- Development mode: `DEBUG = True`, insecure SECRET_KEY (needs securing for production)

## Development Workflows

### Initial Setup
```powershell
# Create/activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

### Running the Server
```powershell
python manage.py runserver
```

### Database Operations
```powershell
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Access Django shell
python manage.py shell
```

## Project Conventions

### App Registration
New apps should be added to `INSTALLED_APPS` using the append pattern:
```python
INSTALLED_APPS += [
    'feedback',
    # Add new apps here
]
```

### Version Management
Dependencies are pinned to exact versions in `requirements.txt` (e.g., `Django==5.2.8`)

### Git Ignores
Standard Django exclusions: `__pycache__/`, `*.pyc`, `.venv/`, `db.sqlite3`, `.vscode/`

## Current State
The `feedback` app is scaffolded but minimal:
- No models defined yet in `feedback/models.py`
- No views implemented in `feedback/views.py`
- No URL patterns configured in `core/urls.py` (only admin panel)
- Admin is available at `/admin/` but no models are registered

When adding features to the feedback app, follow Django conventions for models → views → URLs → templates workflow.
