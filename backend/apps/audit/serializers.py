from rest_framework import serializers

from apps.users.models import LoginAttempt

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_username",
            "action",
            "action_label",
            "entity",
            "entity_id",
            "description",
            "metadata",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields


class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = [
            "id",
            "username_attempted",
            "successful",
            "ip_address",
            "user_agent",
            "reason",
            "created_at",
        ]
        read_only_fields = fields
