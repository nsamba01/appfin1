from django.urls import path

from .views import AuditLogListView, LoginAttemptListView

urlpatterns = [
    path("admin/audit-logs/", AuditLogListView.as_view(), name="admin-audit-logs"),
    path("admin/login-logs/", LoginAttemptListView.as_view(), name="admin-login-logs"),
]
