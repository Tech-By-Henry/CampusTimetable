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
