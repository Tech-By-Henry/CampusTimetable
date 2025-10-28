from rest_framework import serializers
from catalog.models import Course

class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    typical_level_name = serializers.CharField(source="typical_level.name", read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "department", "department_name",
            "code", "title", "units",
            "typical_level", "typical_level_name",
            "is_active"
        ]

    def validate_units(self, v):
        if v < 1 or v > 10:
            raise serializers.ValidationError("units must be between 1 and 10.")
        return v

    def validate_code(self, s):
        raw = "".join(str(s).split()).upper()
        if len(raw) >= 4 and raw[-3:].isdigit():
            s_norm = f"{raw[:-3]} {raw[-3:]}"
        else:
            s_norm = raw
        return s_norm
