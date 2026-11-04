from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsFinanceOrAdministrator

from .services import build_charts, build_comparison_table, build_summary


class DashboardSummaryView(APIView):
    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        payload, error = build_summary(request.query_params)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class DashboardChartsView(APIView):
    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        payload, error = build_charts(request.query_params)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class DashboardComparisonView(APIView):
    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        payload, error = build_comparison_table(request.query_params)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)
