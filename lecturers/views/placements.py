from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

from institution_admin.models import TeachingAssignment, TimetableEntry
from ..serializers.placements import LecturerPlacementSerializer
from ..permissions import IsLecturerUser


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _is_truthy(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


class LecturerPlacementsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/lecturer/me/placements/

    Response: list of TeachingAssignment-like objects (one per assignment the lecturer holds),
    each including `placements` (list of TimetableEntry rows) and `placed` boolean.

    Query params:
      - term=<int>          (filters offering.term_id)
      - active_only=1|true  (only active assignments)
      - role=<str>          (case-insensitive exact)
      - offering=<int>      (offering id)
      - ordering=course_code|-course_code|position|-position|created_at|-created_at
    """
    serializer_class = LecturerPlacementSerializer
    permission_classes = [IsAuthenticated, IsLecturerUser]
    http_method_names = ["get", "head", "options"]

    # allowed ordering tokens (client-visible)
    _ALLOWED_ORDERING = {
        "position", "-position",
        "course_code", "-course_code",
        "created_at", "-created_at",
    }

    def get_queryset(self):
        user = self.request.user
        q = self.request.query_params

        # base — assignments for this lecturer
        qs = (
            TeachingAssignment.objects
            .select_related(
                "offering",
                "offering__course",
                "offering__cohort",
                "offering__term",
                "lecturer",
            )
            .filter(lecturer_id=user.id)
        )

        # filters on offering/term/role/active
        term_id = _to_int(q.get("term"))
        if term_id is not None:
            qs = qs.filter(offering__term_id=term_id)

        offering_id = _to_int(q.get("offering"))
        if offering_id is not None:
            qs = qs.filter(offering_id=offering_id)

        role = q.get("role")
        if role:
            qs = qs.filter(role__iexact=role.strip())

        if _is_truthy(q.get("active_only", "")):
            qs = qs.filter(active=True)

        # prefetch placements (TimetableEntry) and attach them to offering.prefetched_placements
        # if term filtering applied, limit timetable entries to that term as an optimization
        tt_qs = TimetableEntry.objects.select_related("slot", "room").order_by("slot__day", "slot__slot_index", "id")
        if term_id is not None:
            tt_qs = tt_qs.filter(term_id=term_id)

        qs = qs.prefetch_related(
            Prefetch("offering__placements", queryset=tt_qs, to_attr="prefetched_placements")
        )

        # ordering
        ordering = q.get("ordering")
        if ordering in self._ALLOWED_ORDERING:
            if ordering.replace("-", "") == "course_code":
                prefix = "-" if ordering.startswith("-") else ""
                qs = qs.order_by(f"{prefix}offering__course__code", "position", "id")
            else:
                # position or created_at; add stable tie-breaker id
                if ordering.startswith("-"):
                    qs = qs.order_by(ordering, "id")
                else:
                    qs = qs.order_by(ordering, "id")
        else:
            qs = qs.order_by("offering__course__code", "position", "id")

        return qs
