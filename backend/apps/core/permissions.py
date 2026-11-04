"""Role-based access control and password-state enforcement."""
from __future__ import annotations

from rest_framework.permissions import BasePermission


class PasswordChangePending(Exception):
    pass


def _password_is_current(user) -> bool:
    return not getattr(user, "must_change_password", False)


class PasswordCurrentPermission(BasePermission):
    """Blocks every endpoint while a password change is pending.

    DRF authenticates the request inside the view, so this rule lives in the
    permission layer (a Django middleware cannot see JWT users). Views that must
    stay reachable (me / password change / logout) opt out with
    ``allow_password_change_pending = True``.
    """

    message = "Vous devez changer votre mot de passe avant de continuer."
    code = "password_change_required"

    def has_permission(self, request, view):
        if getattr(view, "allow_password_change_pending", False):
            return True
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return True  # authentication classes decide
        return _password_is_current(user)


class RolePermission(BasePermission):
    """Shared base: authenticated, password current, then the role rule."""

    message = "Accès refusé."
    code = "permission_denied"
    required_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if not _password_is_current(user) and not getattr(
            view, "allow_password_change_pending", False
        ):
            self.message = "Vous devez changer votre mot de passe avant de continuer."
            self.code = "password_change_required"
            return False
        if user.role not in self.required_roles:
            self.message = "Vous n'êtes pas autorisé à effectuer cette action."
            self.code = "role_forbidden"
            return False
        return True


class IsAdministrator(RolePermission):
    message = "Accès réservé aux administrateurs."
    required_roles = ("ADMIN",)


class IsFinanceUser(RolePermission):
    message = "Accès réservé aux utilisateurs financiers."
    required_roles = ("FINANCE",)


class IsFinanceOrAdministrator(RolePermission):
    message = "Accès réservé aux utilisateurs authentifiés."
    required_roles = ("FINANCE", "ADMIN")


class IsAuthenticatedAndPasswordCurrent(BasePermission):
    message = "Vous devez changer votre mot de passe avant de continuer."
    code = "password_change_required"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and (
                _password_is_current(user)
                or getattr(view, "allow_password_change_pending", False)
            )
        )
