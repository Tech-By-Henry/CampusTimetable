"""
Teaching assignments CRUD plus a convenience action to atomically swap positions
between two assignments on the **same offering**.

Useful for Step 14 "swap lecturers" when you keep two Primaries and want to flip
their ordering without manual PATCH juggling.
"""
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import TeachingAssignment
from institution_admin.serializers.assignments import TeachingAssignmentSerializer


class TeachingAssignmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for teaching assignments (free-text roles).
    Filters:
      ?offering=<id>&lecturer=<id>&role=<label>&active=1|0
    """
    queryset = TeachingAssignment.objects.select_related(
        "offering", "offering__course", "lecturer"
    ).all()
    serializer_class = TeachingAssignmentSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "offering__course__code",
        "offering__course__title",
        "lecturer__email",
        "lecturer__first_name",
        "lecturer__last_name",
        "role",
    ]
    ordering_fields = ["offering_id", "role", "position", "id"]
    ordering = ["offering_id", "role", "position", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("offering"):
            qs = qs.filter(offering_id=q["offering"])
        if q.get("lecturer"):
            qs = qs.filter(lecturer_id=q["lecturer"])
        if q.get("role"):
            qs = qs.filter(role=q["role"])
        if q.get("active") in ("0", "1", "true", "false", "True", "False"):
            val = q["active"] in ("1", "true", "True")
            qs = qs.filter(active=val)
        return qs

    @action(detail=False, methods=["get"], url_path="role-suggestions")
    def role_suggestions(self, request):
        """
        GET /api/v1/admin/assignments/role-suggestions/?q=&cohort=&offering=&stream=
        """
        qs = self.get_queryset()

        q = request.query_params.get("q")
        if q:
            qs = qs.filter(role__icontains=q)

        if request.query_params.get("cohort"):
            qs = qs.filter(offering__cohort_id=request.query_params["cohort"])
        if request.query_params.get("offering"):
            qs = qs.filter(offering_id=request.query_params["offering"])
        if request.query_params.get("stream"):
            qs = qs.filter(offering__stream_id=request.query_params["stream"])

        roles = list(qs.order_by("role").values_list("role", flat=True).distinct())
        return Response({"count": len(roles), "results": [{"role": r} for r in roles]})

    @action(detail=False, methods=["post"], url_path="swap")
    def swap(self, request):
        """
        POST /api/v1/admin/assignments/swap/
        Body: { "a": <assignment_id>, "b": <assignment_id> }
        Atomically swaps `.position` between the two assignments.
        Both assignments must belong to the same offering.
        """
        a_id = request.data.get("a")
        b_id = request.data.get("b")
        if not a_id or not b_id:
            return Response({"detail": "a and b are required"}, status=status.HTTP_400_BAD_REQUEST)

        # lock rows for the swap
        with transaction.atomic():
            a = self.get_queryset().select_for_update().filter(pk=a_id).first()
            b = self.get_queryset().select_for_update().filter(pk=b_id).first()
            if not a or not b:
                return Response({"detail": "assignment not found"}, status=status.HTTP_404_NOT_FOUND)
            if a.offering_id != b.offering_id:
                return Response({"detail": "assignments must target the same offering"}, status=status.HTTP_400_BAD_REQUEST)

            a.position, b.position = b.position, a.position
            a.save(update_fields=["position"])
            b.save(update_fields=["position"])

        return Response({"ok": True, "a": a_id, "b": b_id}, status=status.HTTP_200_OK)
