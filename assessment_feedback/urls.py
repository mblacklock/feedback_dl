from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_file, name="upload_file"),
    path("confirm/", views.confirm_mappings, name="confirm_mappings"),
    path("process/", views.process_feedback, name="process_feedback"),
]
