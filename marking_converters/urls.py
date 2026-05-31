from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="marking_converters"),
    path("gradebook/upload/", views.merge_upload, name="gradebook_upload"),
    path("gradebook/match/", views.merge_match, name="gradebook_match"),
    path("mcrf/upload/", views.populate_upload, name="mcrf_upload"),
    path("mcrf/match/", views.populate_match, name="mcrf_match"),
]
