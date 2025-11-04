# institution_admin/views/cohorts.py
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import ProgramCohort, CohortLevel
from institution_admin.serializers.cohorts import (
    ProgramCohortSerializer,
    CohortLevelItemSerializer,
    CohortLevelPathSetSerializer,
)


class ProgramCohortViewSet(viewsets.ModelViewSet):
    """
    Manage program cohorts (manual + auto-created).
    """
    queryset = ProgramCohort.objects.select_related("program").all()
    serializer_class = ProgramCohortSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["label", "program__name", "program__code"]
    ordering_fields = ["session_start_year", "session_end_year", "label", "id"]
    ordering = ["-session_start_year", "label"]

    @action(detail=True, methods=["get"], url_path="levels")
    def list_levels(self, request, pk=None):
        cohort = self.get_object()
        data = CohortLevelItemSerializer(cohort.levels.all(), many=True).data
        return Response({"count": len(data), "results": data})

    @action(detail=True, methods=["post"], url_path="level-path")
    def set_level_path(self, request, pk=None):
        """
        Replace a cohort's level path in one shot.
        Expected payload:
        {
          "levels": [
            { "level": 1, "position": 1, "semesters": 2 },
            { "level": 2, "position": 2, "semesters": 2 }
          ]
        }
        """
        cohort = self.get_object()
        ser = CohortLevelPathSetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data["levels"]

        with transaction.atomic():
            cohort.levels.all().delete()
            objs = []
            for it in items:
                objs.append(
                    CohortLevel(
                        cohort=cohort,
                        level_id=it["level"],
                        position=it["position"],
                        semesters=int(it.get("semesters", 2)),
                    )
                )
            CohortLevel.objects.bulk_create(objs)

        return Response({"ok": True, "updated": len(items)}, status=status.HTTP_200_OK)
