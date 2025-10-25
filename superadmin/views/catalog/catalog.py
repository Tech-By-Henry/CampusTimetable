# superadmin/views/catalog/catalog.py
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from superadmin.permissions import IsSuperAdmin
from catalog.models import Faculty, Department, Program, Room, AcademicTerm
from superadmin.serializers.catalog.catalog import (
    FacultySerializer, DepartmentSerializer, ProgramSerializer, RoomSerializer, AcademicTermSerializer
)

class BaseSuperAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code", "id"]
    ordering = ["name"]

class FacultyViewSet(BaseSuperAdminViewSet):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer

class DepartmentViewSet(BaseSuperAdminViewSet):
    queryset = Department.objects.select_related("faculty").all()
    serializer_class = DepartmentSerializer
    search_fields = ["name", "code", "faculty__name", "faculty__code"]

class ProgramViewSet(BaseSuperAdminViewSet):
    queryset = Program.objects.select_related("department", "department__faculty").all()
    serializer_class = ProgramSerializer
    search_fields = ["name", "code", "department__name", "department__code"]

class RoomViewSet(BaseSuperAdminViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    search_fields = ["name", "code"]

class AcademicTermViewSet(BaseSuperAdminViewSet):
    queryset = AcademicTerm.objects.all()
    serializer_class = AcademicTermSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["start_date", "end_date", "name", "code"]
    ordering = ["-start_date"]
