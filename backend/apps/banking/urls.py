from django.urls import path

from .views import (
    AdminBankConfigTestView,
    AdminBankConfigView,
    AdminBankSecretsClearView,
    AdminBankSyncView,
    AdminSyncLogsView,
    BankingHistoryView,
    BankingStatusView,
)

urlpatterns = [
    path("banking/status/", BankingStatusView.as_view(), name="banking-status"),
    path("banking/history/", BankingHistoryView.as_view(), name="banking-history"),
    path("banking/config/", AdminBankConfigView.as_view(), name="banking-config"),
    path("banking/config/test/", AdminBankConfigTestView.as_view(), name="banking-config-test"),
    path("banking/config/clear-secrets/", AdminBankSecretsClearView.as_view(), name="banking-config-clear"),
    path("banking/sync/", AdminBankSyncView.as_view(), name="banking-sync"),
    path("banking/logs/", AdminSyncLogsView.as_view(), name="banking-logs"),
]
