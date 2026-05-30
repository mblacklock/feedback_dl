from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="marking_converters"),
    path("merge/upload/", views.merge_upload, name="converter_merge_upload"),
    path("merge/match/", views.merge_match, name="converter_merge_match"),
    path("populate/upload/", views.populate_upload, name="converter_populate_upload"),
    path("populate/match/", views.populate_match, name="converter_populate_match"),
]
