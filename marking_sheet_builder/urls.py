from django.urls import path

from . import views


urlpatterns = [
    path("", views.builder, name="marking_sheet_builder"),
]
