from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.home, name="home"),
    path("reports/", views.reports, name="reports"),
    path("reports/export/csv/", views.report_export_csv, name="report_csv"),
    path("reports/export/pdf/", views.report_export_pdf, name="report_pdf"),
]
