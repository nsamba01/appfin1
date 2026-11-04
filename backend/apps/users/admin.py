from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginAttempt, User, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("username",)
    list_display = ("username", "full_name", "role", "is_active", "must_change_password", "last_login_at")
    list_filter = ("role", "is_active", "must_change_password")
    search_fields = ("username", "full_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profil", {"fields": ("full_name", "email", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "must_change_password")}),
        ("Sécurité", {"fields": ("failed_login_attempts", "locked_until", "last_login_at", "last_login_ip")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "full_name", "role", "password1", "password2")}),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username_attempted", "successful", "ip_address", "reason", "created_at")
    list_filter = ("successful",)
    search_fields = ("username_attempted", "ip_address")
    readonly_fields = [f.name for f in LoginAttempt._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "created_at", "expires_at", "revoked_at")
    search_fields = ("user__username",)
