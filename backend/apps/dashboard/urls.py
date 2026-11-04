from django.urls import path

from .views import DashboardChartsView, DashboardComparisonView, DashboardSummaryView

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/charts/", DashboardChartsView.as_view(), name="dashboard-charts"),
    path("dashboard/comparison/", DashboardComparisonView.as_view(), name="dashboard-comparison"),
]
