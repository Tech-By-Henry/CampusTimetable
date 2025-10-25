# superadmin/views/auth/OTsetup.py
from django.contrib.auth import get_user_model
from rest_framework import status, throttling, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from superadmin.serializers.auth.OTsetup import OTSetupSerializer
from superadmin.models import InstitutionSetting

User = get_user_model()

class SetupBurstThrottle(throttling.AnonRateThrottle):
    # Mild throttle to deter setup_code brute-forcing
    rate = "10/min"

class OTSetupViewSet(viewsets.ViewSet):
    """
    Router path (POST): /api/v1/superadmin/auth/ot-setup/
    Body: OTSetupSerializer payload
    """
    authentication_classes = []   # public, one-time
    permission_classes = [AllowAny]
    throttle_classes = [SetupBurstThrottle]

    def create(self, request):
        # hard gate: if already set once, block early
        if User.objects.filter(is_superuser=True).exists() or InstitutionSetting.objects.exists():
            return Response(
                {"detail": "Setup already completed."},
                status=status.HTTP_410_GONE
            )

        ser = OTSetupSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = ser.save()
        return Response(payload, status=status.HTTP_200_OK)
