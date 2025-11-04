# institution_admin/views/cohort_auto.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import CohortAutoCreateConfig
from institution_admin.serializers.cohort_auto import CohortAutoCreateConfigSerializer

class CohortAutoCreateConfigViewSet(viewsets.ModelViewSet):
    queryset = CohortAutoCreateConfig.objects.all()
    serializer_class = CohortAutoCreateConfigSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
