from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminUserViewSet, ApplicationSettingsView

router = DefaultRouter()
router.register("admin/users", AdminUserViewSet, basename="admin-users")

urlpatterns = [
    path("admin/settings/", ApplicationSettingsView.as_view(), name="admin-settings"),
    path("", include(router.urls)),
]
