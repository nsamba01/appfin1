from django.contrib import admin

from .models import ApiTokenCache, BalanceSnapshot, EcobankConfiguration, SyncLog


@admin.register(EcobankConfiguration)
class EcobankConfigurationAdmin(admin.ModelAdmin):
    list_display = ("environment", "is_enabled", "masked_account_no", "last_sync_at", "last_sync_status")
    readonly_fields = ("secret_key_encrypted", "subscription_key_encrypted", "account_no_encrypted")

    def has_add_permission(self, request):
        return not EcobankConfiguration.objects.exists()


@admin.register(BalanceSnapshot)
class BalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("fetched_at", "available_balance", "currency", "source", "is_sandbox", "status")
    list_filter = ("source", "is_sandbox", "status")

    def has_add_permission(self, request):
        return False


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "trigger", "status", "http_status", "response_code", "duration_ms")
    list_filter = ("trigger", "status")

    def has_add_permission(self, request):
        return False


@admin.register(ApiTokenCache)
class ApiTokenCacheAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "expires_at", "created_at")
    readonly_fields = ("encrypted_token",)
