from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_file, name="upload_file"),
    path("mapping/", views.confirm_mappings, name="confirm_mappings"),
    path("layout/", views.configure_layout, name="configure_layout"),
    path("process/", views.process_feedback, name="process_feedback"),
    path("success/", views.generation_success, name="generation_success"),
    path("download-email-utility/", views.download_email_xlsm, name="download_email_xlsm"),
    path("rubric-bands/", views.rubric_bands_api, name="rubric_bands_api"),
]
