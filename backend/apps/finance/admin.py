from django.contrib import admin

from .models import Operation


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ("date", "label", "operation_type", "amount", "reference", "is_deleted")
    list_filter = ("operation_type", "is_deleted")
    search_fields = ("label", "reference", "observation")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at", "deleted_at", "deleted_by")
