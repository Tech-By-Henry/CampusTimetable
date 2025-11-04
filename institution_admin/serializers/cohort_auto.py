# institution_admin/serializers/cohort_auto.py
from rest_framework import serializers
from institution_admin.models import CohortAutoCreateConfig

class CohortAutoCreateConfigSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = CohortAutoCreateConfig
        fields = [
            "id",
            "frequency_days",
            "frequency_seconds",
            "next_creation_at",
            "next_creation_date",
            "label_mode",
            "label_custom_template",
            "auto_enroll_students",
            "active",
            "created_by",
            "last_created_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "last_created_at", "created_at", "updated_at"]

    def validate(self, attrs):
        # require either next_creation_at or next_creation_date for config clarity
        if not attrs.get("next_creation_at") and not attrs.get("next_creation_date"):
            raise serializers.ValidationError("Either next_creation_at (datetime) or next_creation_date (date) must be set.")
        if attrs.get("label_mode") == CohortAutoCreateConfig.LABEL_CUSTOM and not attrs.get("label_custom_template"):
            raise serializers.ValidationError("label_custom_template must be set when label_mode is CUSTOM.")
        return super().validate(attrs)

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["created_by"] = getattr(request, "user", None)
        return super().create(validated_data)
