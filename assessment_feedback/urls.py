from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_file, name="upload_file"),
    path("confirm/", views.confirm_mappings, name="confirm_mappings"),
    path("layout/", views.configure_layout, name="configure_layout"),
    path("process/", views.process_feedback, name="process_feedback"),
    path("rubric-bands/", views.rubric_bands_api, name="rubric_bands_api"),
]
