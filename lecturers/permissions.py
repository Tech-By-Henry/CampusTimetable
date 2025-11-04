# lecturers/permissions.py
from rest_framework import permissions
from onboarding.models import IntakeSubmission, IntakeLink

class IsLecturerUser(permissions.BasePermission):
    """
    Grants access only to users who have an activated IntakeSubmission with
    role == IntakeLink.ROLE_LECTURER.
    """
    message = "You must be an activated lecturer."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        return IntakeSubmission.objects.filter(
            user=user,
            role=IntakeLink.ROLE_LECTURER,
            activated_at__isnull=False
        ).exists()
