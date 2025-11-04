# institution_admin/serializers/cohort_manual.py

from rest_framework import serializers
from institution_admin.models import ProgramCohort
from institution_admin.serializers.cohorts import ProgramCohortSerializer  # reuse your existing serializer

class ManualCohortCreateSerializer(serializers.Serializer):
    program = serializers.IntegerField()
    session_start_year = serializers.IntegerField()
    session_end_year = serializers.IntegerField(required=False)
    label = serializers.CharField(required=False, allow_blank=True)
    is_auto = serializers.BooleanField(default=False)

    def validate_program(self, value):
        from catalog.models import Program
        if not Program.objects.filter(id=value).exists():
            raise serializers.ValidationError("Unknown program id")
        return value

class ManualCohortResponseSerializer(ProgramCohortSerializer):
    # reuse existing ProgramCohortSerializer for output
    pass
