from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import Operation, OperationType


class OperationSerializer(serializers.ModelSerializer):
    operation_type_label = serializers.CharField(
        source="get_operation_type_display", read_only=True
    )
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )
    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True, default=None
    )
    signed_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = Operation
        fields = [
            "id",
            "date",
            "label",
            "amount",
            "operation_type",
            "operation_type_label",
            "reference",
            "observation",
            "signed_amount",
            "created_by_username",
            "updated_by_username",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "signed_amount",
            "operation_type_label",
            "created_by_username",
            "updated_by_username",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ]


class OperationWriteSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Operation
        fields = ["date", "label", "amount", "operation_type", "reference", "observation"]

    def validate_label(self, value):
        value = (value or "").strip()
        if len(value) < 3:
            raise serializers.ValidationError("Le libellé doit contenir au moins 3 caractères.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
        if value > Decimal("999999999999.99"):
            raise serializers.ValidationError("Le montant dépasse la limite autorisée.")
        return value

    def validate_operation_type(self, value):
        if value not in OperationType.values:
            raise serializers.ValidationError("Type d'opération invalide.")
        return value

    def validate_reference(self, value):
        return (value or "").strip()[:64]

    def validate_observation(self, value):
        return (value or "").strip()[:2000]
