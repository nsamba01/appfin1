from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BalanceView, FinanceHistoryView, OperationViewSet

router = DefaultRouter()
router.register("finance/operations", OperationViewSet, basename="operation")

urlpatterns = [
    path("finance/balances/", BalanceView.as_view(), name="finance-balances"),
    path("finance/history/", FinanceHistoryView.as_view(), name="finance-history"),
    path("", include(router.urls)),
]
