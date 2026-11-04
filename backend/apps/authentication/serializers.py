from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Kept for compatibility with SimpleJWT; the SPA uses /api/auth/login/."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user: User = self.user
        if not user.is_active:
            raise AuthenticationFailed("Compte désactivé.")
        data["user"] = {
            "id": user.pk,
            "username": user.username,
            "role": user.role,
            "must_change_password": user.must_change_password,
        }
        return data
