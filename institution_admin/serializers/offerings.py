from rest_framework import serializers
from institution_admin.models import CourseOffering, CohortLevel

class CourseOfferingSerializer(serializers.ModelSerializer):
    course_code  = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    cohort_label = serializers.CharField(source="cohort.label", read_only=True)
    level_name   = serializers.CharField(source="level.name", read_only=True)
    stream_code  = serializers.CharField(source="stream.code", read_only=True)

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "term", "cohort", "level", "semester",
            "course", "course_code", "course_title",
            "stream", "stream_code",
            "capacity_need", "room_features",
            "created_at",
            "cohort_label", "level_name",
        ]

    def validate(self, attrs):
        inst    = self.instance
        cohort  = attrs.get("cohort")  or (inst and inst.cohort)
        level   = attrs.get("level")   or (inst and inst.level)
        sem     = int(attrs.get("semester") or (inst and inst.semester) or 1)
        stream  = attrs.get("stream")  if "stream" in attrs else (inst and inst.stream)

        if stream and stream.cohort_id != cohort.id:
            raise serializers.ValidationError("stream does not belong to this cohort.")

        cl = CohortLevel.objects.filter(cohort=cohort, level=level).first()
        if not cl:
            raise serializers.ValidationError("level is not part of this cohort's path.")
        if sem < 1 or sem > cl.semesters:
            raise serializers.ValidationError(f"semester must be between 1 and {cl.semesters} for {level.name}.")

        return attrs
