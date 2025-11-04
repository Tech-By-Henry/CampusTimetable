# lecturers/views/auth.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from onboarding.models import IntakeSubmission, IntakeLink
from lecturers.serializers.auth import LecturerMeSerializer

class LecturerAuthViewSet(viewsets.ViewSet):
    """
    GET /api/v1/lecturer/auth/me/
    Returns minimal identity + whether this user is an activated lecturer, plus staff_id (id_code) if known.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        user = request.user

        # Find an activated lecturer submission for this user (if any)
        sub = (
            IntakeSubmission.objects
            .filter(user_id=user.id, role=IntakeLink.ROLE_LECTURER)
            .order_by("-activated_at", "-created_at")
            .first()
        )
        is_lecturer = bool(sub and sub.activated_at)
        staff_id = sub.id_code if sub else None

        payload = {
            "id": user.id,
            "email": user.email or "",
            "username": getattr(user, "username", "") or "",
            "first_name": getattr(user, "first_name", "") or "",
            "last_name": getattr(user, "last_name", "") or "",
            "is_lecturer": is_lecturer,
            "staff_id": staff_id,
        }
        ser = LecturerMeSerializer(payload)
        return Response(ser.data, status=status.HTTP_200_OK)
