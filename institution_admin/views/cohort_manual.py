# institution_admin/views/cohort_manual.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.serializers.cohort_manual import ManualCohortCreateSerializer, ManualCohortResponseSerializer
from institution_admin.services.cohort_manual_create import create_manual_cohort
from django.db import IntegrityError

class CohortManualCreateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]

    def create(self, request):
        """
        POST /api/admin/cohorts-manual/
        payload: { program: id, session_start_year: 2025, session_end_year?: 2026, label?: "...", is_auto?: false }
        """
        ser = ManualCohortCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            cohort = create_manual_cohort(
                program_id=data["program"],
                start_year=int(data["session_start_year"]),
                session_end_year=data.get("session_end_year"),
                label=data.get("label"),
                created_by=request.user,
                is_auto=data.get("is_auto", False),
                auto_config=None,
            )
        except IntegrityError as e:
            return Response({"detail": "Cohort already exists for this program/session."}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "Failed to create cohort", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        out = ManualCohortResponseSerializer(cohort).data
        return Response(out, status=status.HTTP_201_CREATED)
