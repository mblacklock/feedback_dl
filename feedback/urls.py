from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("template/new/", views.template_new, name="template_new"),
    path("template/<int:pk>/", views.template_summary, name="template_summary"),
    path("template/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("template/<int:pk>/update/", views.template_update, name="template_update"),
    path("grade-bands-preview/", views.grade_bands_preview, name="grade_bands_preview"),
]
