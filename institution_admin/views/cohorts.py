from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import ProgramCohort, CohortLevel, CohortStream
from institution_admin.serializers.cohorts import (
    ProgramCohortSerializer,
    CohortLevelItemSerializer,
    CohortLevelPathSetSerializer,
    CohortStreamSerializer,
)

class ProgramCohortViewSet(viewsets.ModelViewSet):
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

    @action(detail=True, methods=["get", "post"], url_path="streams")
    def streams(self, request, pk=None):
        cohort = self.get_object()

        if request.method == "GET":
            data = CohortStreamSerializer(cohort.streams.all(), many=True).data
            return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

        ser = CohortStreamSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if cohort.streams.filter(code=ser.validated_data["code"]).exists():
            return Response({"detail": "Stream code already exists for this cohort."}, status=status.HTTP_400_BAD_REQUEST)

        obj = CohortStream.objects.create(cohort=cohort, **ser.validated_data)
        return Response(CohortStreamSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"streams/(?P<stream_id>\d+)")
    def stream_detail(self, request, pk=None, stream_id=None):
        cohort = self.get_object()
        try:
            stream = cohort.streams.get(id=stream_id)
        except CohortStream.DoesNotExist:
            return Response({"detail": "Stream not found for this cohort."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            stream.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        ser = CohortStreamSerializer(stream, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        new_code = ser.validated_data.get("code")
        if new_code and new_code != stream.code and cohort.streams.filter(code=new_code).exists():
            return Response({"detail": "Stream code already exists for this cohort."}, status=status.HTTP_400_BAD_REQUEST)
        ser.save()
        return Response(ser.data, status=status.HTTP_200_OK)
