from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("template/new/", views.template_new, name="template_new"),
    path("template/<int:pk>/", views.template_summary, name="template_summary"),
]
