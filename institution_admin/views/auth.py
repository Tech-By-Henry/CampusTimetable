from django.contrib.auth import get_user_model
from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from onboarding.models import IntakeSubmission, IntakeLink
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.serializers.auth import AdminLoginSerializer

User = get_user_model()

def _find_admin_submission_by_staff_id(staff_id: str):
    sid = (staff_id or "").strip().upper()
    if not sid:
        return None
    return (
        IntakeSubmission.objects.select_related("user")
        .filter(
            role=IntakeLink.ROLE_ADMIN,
            id_code=sid,
            activated_at__isnull=False,
            user__isnull=False,
        )
        .order_by("-activated_at", "-id")
        .first()
    )

def _user_is_admin(user) -> bool:
    return IntakeSubmission.objects.filter(
        user=user,
        role=IntakeLink.ROLE_ADMIN,
        activated_at__isnull=False,
    ).exists()

class AdminAuthViewSet(viewsets.ViewSet):
    """
    - POST /api/v1/admin/auth/login/
    - GET  /api/v1/admin/auth/me/
    """

    @action(detail=False, methods=["post"], url_path="login", permission_classes=[permissions.AllowAny])
    def login(self, request):
        ser = AdminLoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        staff_id = ser.validated_data["staff_id"]
        password = ser.validated_data["password"]

        sub = _find_admin_submission_by_staff_id(staff_id)
        if not sub or not sub.user:
            return Response({"detail": "You are not an admin."}, status=status.HTTP_403_FORBIDDEN)

        user: User = sub.user
        if not _user_is_admin(user):
            return Response({"detail": "You are not an admin."}, status=status.HTTP_403_FORBIDDEN)

        if not user.check_password(password):
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"detail": "Account is inactive."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": user.id,
                    "username": user.get_username(),
                    "email": getattr(user, "email", None),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": "ADMIN",
                    "staff_id": sub.id_code,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="me", permission_classes=[IsInstitutionAdmin])
    def me(self, request):
        user: User = request.user
        sub = (
            IntakeSubmission.objects.filter(
                user=user, role=IntakeLink.ROLE_ADMIN, activated_at__isnull=False
            )
            .order_by("-activated_at", "-id")
            .first()
        )
        staff_id = sub.id_code if sub else ""
        return Response(
            {
                "id": user.id,
                "email": getattr(user, "email", None),
                "username": user.get_username(),
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "staff_id": staff_id,
                "role": "ADMIN",
            },
            status=status.HTTP_200_OK,
        )
