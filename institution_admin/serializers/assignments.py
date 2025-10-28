from django.contrib.auth import get_user_model
from rest_framework import serializers
from onboarding.models import IntakeSubmission, IntakeLink
from institution_admin.models import TeachingAssignment

User = get_user_model()

class TeachingAssignmentSerializer(serializers.ModelSerializer):
    lecturer_email = serializers.EmailField(source="lecturer.email", read_only=True)
    lecturer_name  = serializers.SerializerMethodField()
    course_code    = serializers.CharField(source="offering.course.code", read_only=True)
    course_title   = serializers.CharField(source="offering.course.title", read_only=True)

    # free-text role
    role = serializers.CharField(max_length=64, allow_blank=False, trim_whitespace=True)

    class Meta:
        model  = TeachingAssignment
        fields = [
            "id", "offering", "lecturer", "lecturer_name", "lecturer_email",
            "role", "position", "load_share", "notes", "active",
            "course_code", "course_title", "created_at",
        ]

    def get_lecturer_name(self, obj):
        name = f"{obj.lecturer.first_name} {obj.lecturer.last_name}".strip()
        return name or obj.lecturer.get_username()

    def validate_role(self, s: str):
        s = (s or "").strip()
        if not s:
            raise serializers.ValidationError("role is required.")
        return s

    def validate(self, attrs):
        inst     = self.instance
        offering = attrs.get("offering") or (inst and inst.offering)
        lecturer = attrs.get("lecturer") or (inst and inst.lecturer)
        position = attrs.get("position") or (inst.position if inst else 1)

        if lecturer and not IntakeSubmission.objects.filter(
            user=lecturer, role=IntakeLink.ROLE_LECTURER, activated_at__isnull=False
        ).exists():
            raise serializers.ValidationError("Selected user is not an activated lecturer.")

        if position < 1:
            raise serializers.ValidationError("position must be >= 1.")

        ls = attrs.get("load_share", inst and inst.load_share)
        if ls is not None and (ls < 1 or ls > 100):
            raise serializers.ValidationError("load_share must be between 1 and 100.")

        return attrs
# ---------- Lecturer roster (read-only) ----------