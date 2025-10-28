from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from catalog.models import Course
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.serializers.courses import CourseSerializer

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("department", "typical_level").all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "title", "department__name", "department__code"]
    ordering_fields = ["code", "title", "units", "id"]
    ordering = ["code"]
