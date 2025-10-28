from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from catalog.models import Level
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.serializers.levels import LevelSerializer

class LevelViewSet(viewsets.ModelViewSet):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["order", "name", "id"]
    ordering = ["order", "name"]
