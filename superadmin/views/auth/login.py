# superadmin/views/auth/login.py
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class SuperAdminLoginView(APIView):
    """
    POST /api/v1/superadmin/auth/login/
    Body: { "identifier": "<username or email>", "password": "..." }
    Returns: { refresh, access, user }
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identifier = (request.data.get("identifier") or "").strip()
        password   = request.data.get("password") or ""

        if not identifier or not password:
            return Response(
                {"detail": "identifier and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            )
        except User.DoesNotExist:
            # generic message (don’t leak which part failed)
            return Response(
                {"detail": "No active account found with the given credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response({"detail": "Account is inactive"}, status=status.HTTP_403_FORBIDDEN)

        if not user.check_password(password):
            return Response(
                {"detail": "No active account found with the given credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.get_username(),
                "email": getattr(user, "email", None),
                "is_superuser": user.is_superuser,
                "is_staff": user.is_staff,
            },
        }, status=status.HTTP_200_OK)
