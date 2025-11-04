# institution_admin/permissions.py
from rest_framework import permissions
from onboarding.models import IntakeSubmission, IntakeLink

class IsInstitutionAdmin(permissions.BasePermission):
    message = "You are not an admin."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and IntakeSubmission.objects.filter(
                user=user,
                role=IntakeLink.ROLE_ADMIN,
                activated_at__isnull=False,
            ).exists()
        )

class IsAdminOrLecturerReadOnly(permissions.BasePermission):
    """
    - Admins: full access.
    - Lecturers (activated): allowed safe methods (GET/HEAD/OPTIONS).
    - Others: denied.
    """
    message = "Admins have full access; lecturers may only read their own assignments."

    def _is_admin(self, user):
        return bool(user and user.is_authenticated and IntakeSubmission.objects.filter(
            user=user, role=IntakeLink.ROLE_ADMIN, activated_at__isnull=False
        ).exists())

    def _is_lecturer(self, user):
        return bool(user and user.is_authenticated and IntakeSubmission.objects.filter(
            user=user, role=IntakeLink.ROLE_LECTURER, activated_at__isnull=False
        ).exists())

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if request.method in permissions.SAFE_METHODS:
            return self._is_admin(user) or self._is_lecturer(user)
        # unsafe methods only for admins
        return self._is_admin(user)
