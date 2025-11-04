# lecturers/serializers/assignments.py
from rest_framework import serializers
from institution_admin.models import TeachingAssignment

class OfferingSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

class LecturerAssignmentSerializer(serializers.ModelSerializer):
    # <-- remove source here; field name 'offering' already matches the FK
    offering = OfferingSummarySerializer(read_only=True)

    lecturer_name = serializers.SerializerMethodField(read_only=True)
    lecturer_email = serializers.EmailField(source="lecturer.email", read_only=True)

    class Meta:
        model = TeachingAssignment
        fields = [
            "id",
            "offering",
            "role",
            "position",
            "load_share",
            "notes",
            "active",
            "created_at",
            "lecturer_name",
            "lecturer_email",
        ]
        read_only_fields = fields

    def get_lecturer_name(self, obj):
        user = getattr(obj, "lecturer", None)
        if not user:
            return None
        return (getattr(user, "get_full_name", lambda: "")() or
                getattr(user, "full_name", None) or
                user.get_username())
