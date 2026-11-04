from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

admin.site.site_header = "FinBank — Administration technique"
admin.site.site_title = "FinBank Admin"


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health, name="health"),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.finance.urls")),
    path("api/", include("apps.banking.urls")),
    path("api/", include("apps.dashboard.urls")),
    path("api/", include("apps.audit.urls")),
]
