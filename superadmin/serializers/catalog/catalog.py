# superadmin/serializers/catalog/catalog.py
from rest_framework import serializers
from catalog.models import Faculty, Department, Program, Room, AcademicTerm

class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ["id", "name", "code"]

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "faculty", "name", "code"]

class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ["id", "department", "name", "code", "duration_years"]

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "code", "capacity", "features"]

class AcademicTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicTerm
        fields = ["id", "name", "code", "start_date", "end_date", "is_current"]
