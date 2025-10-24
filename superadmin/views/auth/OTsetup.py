from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, throttling
from django.contrib.auth import get_user_model
from superadmin.serializers.auth.OTsetup import OTSetupSerializer
from superadmin.models import InstitutionSetting
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from superadmin.serializers.auth.login import EmailOrUsernameTokenObtainPairSerializer

User = get_user_model()

class SetupBurstThrottle(throttling.AnonRateThrottle):
    # Mild throttle to deter setup_code brute-forcing
    rate = "10/min"

class OTSetupView(APIView):
    authentication_classes = []   # one-time public endpoint
    permission_classes = []
    throttle_classes = [SetupBurstThrottle]

    def post(self, request):
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
        # 200 OK or 201 Created — using 200 for simpler clients
        return Response(payload, status=status.HTTP_200_OK)



