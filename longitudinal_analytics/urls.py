from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.longitudinal_upload, name="longitudinal_upload"),
    path("confirm/", views.longitudinal_confirm, name="longitudinal_confirm"),
    path("dashboard/", views.longitudinal_dashboard, name="longitudinal_dashboard"),
    path("scatter-data/", views.longitudinal_scatter_data, name="longitudinal_scatter_data"),
]
