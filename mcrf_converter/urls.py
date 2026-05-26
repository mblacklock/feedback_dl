from django.urls import path
from . import views

urlpatterns = [
    path("", views.converter_page, name="mcrf_converter"),
]
