# lecturers/views/assignments.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from institution_admin.models import TeachingAssignment
from ..serializers.assignments import LecturerAssignmentSerializer
from ..permissions import IsLecturerUser


class LecturerAssignmentsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/lecturer/me/assignments/
    Scopes automatically to request.user (lecturer).

    Query params:
      - term=<int>          (filters offering.term_id)
      - active_only=1|true  (filters active=True)
      - role=<str>          (case-insensitive exact)
      - offering=<int>      (offering id)
      - ordering=position|-position|course_code|-course_code|created_at|-created_at
    """
    serializer_class = LecturerAssignmentSerializer
    permission_classes = [IsAuthenticated, IsLecturerUser]
    http_method_names = ["get", "head", "options"]

    _ALLOWED_ORDERING = {
        "position", "-position",
        "course_code", "-course_code",
        "created_at", "-created_at",
    }

    def _to_int(self, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _is_truthy(self, v):
        return str(v).lower() in ("1", "true", "yes", "on")

    def get_queryset(self):
        user = self.request.user

        qs = (TeachingAssignment.objects
              .select_related(
                  "offering",
                  "offering__course",
                  "offering__cohort",
                  "offering__level",
                  "offering__term",
                  "lecturer",
              )
              .filter(lecturer_id=user.id))

        q = self.request.query_params

        # term filter (offering.term_id)
        term = self._to_int(q.get("term"))
        if term is not None:
            qs = qs.filter(offering__term_id=term)

        # active_only
        if self._is_truthy(q.get("active_only", "")):
            qs = qs.filter(active=True)

        # role (case-insensitive exact)
        role = q.get("role")
        if role:
            qs = qs.filter(role__iexact=role.strip())

        # offering id
        offering = self._to_int(q.get("offering"))
        if offering is not None:
            qs = qs.filter(offering_id=offering)

        # safe ordering
        ordering = q.get("ordering")
        if ordering in self._ALLOWED_ORDERING:
            if ordering.replace("-", "") == "course_code":
                prefix = "-" if ordering.startswith("-") else ""
                qs = qs.order_by(f"{prefix}offering__course__code", "position", "id")
            else:
                # position or created_at
                qs = qs.order_by(ordering, "id")
        else:
            qs = qs.order_by("offering__course__code", "position", "id")

        return qs
