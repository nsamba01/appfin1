from rest_framework import serializers

from .models import ApplicationSettings


class ApplicationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationSettings
        fields = [
            "company_name",
            "currency",
            "timezone_label",
            "allow_finance_edit_operations",
            "allow_finance_delete_operations",
            "operation_edit_window_days",
            "bank_sync_interval_minutes",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_currency(self, value):
        value = value.strip().upper()
        if not value.isalpha() or not 3 <= len(value) <= 5:
            raise serializers.ValidationError("Devise invalide (ex : USD, CDF, EUR).")
        return value

    def validate_bank_sync_interval_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError("L'intervalle doit être d'au moins 1 minute.")
        if value > 1440:
            raise serializers.ValidationError("L'intervalle ne peut pas dépasser 1440 minutes.")
        return value

    def validate_operation_edit_window_days(self, value):
        if value > 3650:
            raise serializers.ValidationError("Valeur trop élevée.")
        return value
