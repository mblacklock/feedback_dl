from django.urls import path

from . import views


urlpatterns = [
    path("", views.builder, name="marking_sheet_builder"),
    path("api/grade-bands/", views.grade_bands_json, name="grade_bands_json"),
]
