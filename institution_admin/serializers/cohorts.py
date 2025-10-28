from rest_framework import serializers
from catalog.models import Level
from institution_admin.models import ProgramCohort, CohortLevel, CohortStream

class ProgramCohortSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    program_code = serializers.CharField(source="program.code", read_only=True)

    class Meta:
        model = ProgramCohort
        fields = [
            "id",
            "program",
            "program_name",
            "program_code",
            "label",
            "session_start_year",
            "session_end_year",
            "created_at",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        return ProgramCohort.objects.create(
            created_by=getattr(request, "user", None),
            **validated_data
        )

class CohortLevelItemSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)

    class Meta:
        model = CohortLevel
        fields = ["id", "level", "level_name", "position", "semesters"]

class CohortLevelPathSetSerializer(serializers.Serializer):
    """
    Replace a cohort's level path in one shot.
    {
      "levels": [
        { "level": 1, "position": 1, "semesters": 2 },
        { "level": 2, "position": 2, "semesters": 2 }
      ]
    }
    """
    levels = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField(), allow_empty=False),
        allow_empty=False,
    )

    def validate(self, attrs):
        items = attrs["levels"]

        positions = [it.get("position") for it in items]
        if sorted(positions) != list(range(1, len(items) + 1)):
            raise serializers.ValidationError("Positions must be a contiguous sequence starting at 1.")

        level_ids = [it.get("level") for it in items]
        if len(level_ids) != len(set(level_ids)):
            raise serializers.ValidationError("Duplicate level ids in path.")

        existing = set(Level.objects.filter(id__in=level_ids).values_list("id", flat=True))
        missing = [lid for lid in level_ids if lid not in existing]
        if missing:
            raise serializers.ValidationError(f"Unknown Level ids: {missing}")

        for it in items:
            sems = int(it.get("semesters", 2))
            if sems < 1 or sems > 4:
                raise serializers.ValidationError("semesters must be between 1 and 4.")

        return attrs

class CohortStreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohortStream
        fields = ["id", "name", "code", "is_active"]
