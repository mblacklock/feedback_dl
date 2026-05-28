from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_mcrf, name="module_upload"),
    path("mapping/", views.confirm_module_mappings, name="module_confirm"),
    path("layout/", views.configure_module_layout, name="module_layout"),
    path("process/", views.process_module_summary, name="module_process"),
]
