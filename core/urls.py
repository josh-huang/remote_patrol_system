from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("dashboard/summary/", views.dashboard_summary, name="dashboard-summary"),
    path("routing/shortest-path/", views.shortest_path, name="shortest-path"),
    path("routing/compare-emissions/", views.compare_emissions, name="compare-emissions"),
    path("reports/patrol/", views.patrol_report, name="patrol-report"),
]
