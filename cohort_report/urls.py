from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_cohort_data, name="cohort_report_upload"),
    path("confirm/", views.confirm_cohort_mappings, name="cohort_report_confirm"),
    path("report/", views.render_cohort_report, name="cohort_report_results"),
    path("report/download/", views.download_cohort_report, name="cohort_report_download"),
]
