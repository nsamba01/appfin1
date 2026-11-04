from rest_framework import generics

from apps.core.permissions import IsAdministrator
from apps.users.models import LoginAttempt

from .models import AuditLog
from .serializers import AuditLogSerializer, LoginAttemptSerializer


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdministrator]
    queryset = AuditLog.objects.select_related("actor").all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if action := params.get("action"):
            qs = qs.filter(action=action)
        if actor := params.get("actor"):
            qs = qs.filter(actor_username__icontains=actor)
        if entity := params.get("entity"):
            qs = qs.filter(entity=entity)
        if search := params.get("search"):
            qs = qs.filter(description__icontains=search)
        if date_from := params.get("date_from"):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := params.get("date_to"):
            qs = qs.filter(created_at__date__lte=date_to)
        return qs


class LoginAttemptListView(generics.ListAPIView):
    serializer_class = LoginAttemptSerializer
    permission_classes = [IsAdministrator]
    queryset = LoginAttempt.objects.select_related("user").all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("successful") in {"true", "false"}:
            qs = qs.filter(successful=params["successful"] == "true")
        if username := params.get("username"):
            qs = qs.filter(username_attempted__icontains=username)
        if date_from := params.get("date_from"):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := params.get("date_to"):
            qs = qs.filter(created_at__date__lte=date_to)
        return qs
