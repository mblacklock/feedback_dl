from django.urls import path
from . import views

urlpatterns = [
    path("", views.analytics_upload, name="analytics_upload"),
    path("confirm/", views.analytics_confirm, name="analytics_confirm"),
    path("dashboard/", views.analytics_dashboard, name="analytics_dashboard"),
    path("download/", views.download_snapshot, name="download_snapshot"),
    path("upload-snapshots/", views.upload_snapshots, name="upload_snapshots"),
    path("clear-snapshots/", views.clear_snapshots, name="clear_snapshots"),
]
