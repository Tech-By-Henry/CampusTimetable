"""
Teaching assignments CRUD plus a convenience action to atomically swap positions
between two assignments on the **same offering**.

Admins: full CRUD.
Activated lecturers: safe methods only (list / retrieve) scoped to their own rows.
"""
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from onboarding.models import IntakeSubmission, IntakeLink
from institution_admin.permissions import IsAdminOrLecturerReadOnly
from institution_admin.models import TeachingAssignment
from institution_admin.serializers.assignments import TeachingAssignmentSerializer


def _to_int(val):
    """Safe int conversion — returns int or None (no exception)."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _is_truthy(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


class TeachingAssignmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for teaching assignments (free-text roles).

    Admins:
      - Full access. Can filter with ?term=&offering=&lecturer=&role=&active=
    Lecturers (activated):
      - Only SAFE METHODS (GET/HEAD/OPTIONS).
      - When calling list/detail, they only see assignments where lecturer == request.user.id.
      - If a lecturer explicitly requests another lecturer's rows via ?lecturer=<id>
        they receive a 403 with a clear message.
      - Allowed query params for lecturer: ?term=&offering=&role=&active_only=1
    """
    queryset = TeachingAssignment.objects.select_related(
        "offering", "offering__course", "offering__term", "lecturer"
    ).all()
    serializer_class = TeachingAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrLecturerReadOnly]

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

    # ------------------------
    # Internal helpers
    # ------------------------
    def _user_is_admin(self, user):
        return bool(
            user
            and user.is_authenticated
            and IntakeSubmission.objects.filter(
                user=user,
                role=IntakeLink.ROLE_ADMIN,
                activated_at__isnull=False,
            ).exists()
        )

    def _user_is_lecturer(self, user):
        return bool(
            user
            and user.is_authenticated
            and IntakeSubmission.objects.filter(
                user=user,
                role=IntakeLink.ROLE_LECTURER,
                activated_at__isnull=False,
            ).exists()
        )

    # ------------------------
    # Queryset scoping
    # ------------------------
    def get_queryset(self):
        """
        - Admin: full queryset with filters (?term, ?offering, ?lecturer, ?role, ?active)
        - Lecturer: only their own assignments, filterable by term/offering/role/active_only
          If ?lecturer=<id> is provided and does not match request.user.id,
          raise PermissionDenied with a clear message.
        - Others: empty queryset (but blocked by permissions)
        """
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        q = self.request.query_params

        # ADMIN path
        if self._user_is_admin(user):
            # term filter (via offering)
            term_id = _to_int(q.get("term"))
            if term_id is not None:
                qs = qs.filter(offering__term_id=term_id)

            offering_id = _to_int(q.get("offering"))
            if offering_id is not None:
                qs = qs.filter(offering_id=offering_id)

            lecturer_id = _to_int(q.get("lecturer"))
            if lecturer_id is not None:
                qs = qs.filter(lecturer_id=lecturer_id)

            # role: case-insensitive exact for expected behaviour
            if q.get("role"):
                qs = qs.filter(role__iexact=q["role"].strip())

            # active param (admin uses `active=1|0`); robust parsing
            a = q.get("active")
            if a is not None:
                if a.lower() in ("1", "true", "yes"):
                    qs = qs.filter(active=True)
                elif a.lower() in ("0", "false", "no"):
                    qs = qs.filter(active=False)
                # else malformed -> ignore

            # support active_only alias for admin too
            if q.get("active_only") is not None:
                if _is_truthy(q.get("active_only")):
                    qs = qs.filter(active=True)
                elif str(q.get("active_only")).lower() in ("0", "false", "no"):
                    qs = qs.filter(active=False)

            return qs

        # LECTURER path
        if self._user_is_lecturer(user):
            # If lecturer param explicitly provided and not matching current user -> deny
            if q.get("lecturer"):
                requested_lid = _to_int(q.get("lecturer"))
                if requested_lid is None or requested_lid != user.id:
                    raise PermissionDenied("You are not allowed to view assignments for other lecturers.")

            # scope to request.user ONLY
            qs = qs.filter(lecturer_id=user.id)

            term_id = _to_int(q.get("term"))
            if term_id is not None:
                qs = qs.filter(offering__term_id=term_id)

            offering_id = _to_int(q.get("offering"))
            if offering_id is not None:
                qs = qs.filter(offering_id=offering_id)

            if q.get("role"):
                qs = qs.filter(role__iexact=q["role"].strip())

            if _is_truthy(q.get("active_only", "")):
                qs = qs.filter(active=True)

            # stable ordering for lecturers
            return qs.order_by("offering__course__code", "position", "id")

        # fallback
        return qs.none()

    # ------------------------
    # Custom actions
    # ------------------------
    @action(detail=False, methods=["get"], url_path="role-suggestions")
    def role_suggestions(self, request):
        """
        GET /api/v1/admin/assignments/role-suggestions/?q=&cohort=&offering=
        Returns distinct roles matching filters.
        """
        qs = self.get_queryset()

        qstr = request.query_params.get("q")
        if qstr:
            qs = qs.filter(role__icontains=qstr)

        cohort_id = _to_int(request.query_params.get("cohort"))
        if cohort_id is not None:
            qs = qs.filter(offering__cohort_id=cohort_id)

        offering_id = _to_int(request.query_params.get("offering"))
        if offering_id is not None:
            qs = qs.filter(offering_id=offering_id)

        roles = list(qs.order_by("role").values_list("role", flat=True).distinct())
        return Response({"count": len(roles), "results": [{"role": r} for r in roles]})

    @action(detail=False, methods=["post"], url_path="swap")
    def swap(self, request):
        """
        POST /api/v1/admin/assignments/swap/
        Body: { "a": <assignment_id>, "b": <assignment_id> }
        Atomically swaps `.position` between the two assignments.
        Only allowed for admins.
        """
        a_id = request.data.get("a")
        b_id = request.data.get("b")
        if not a_id or not b_id:
            return Response({"detail": "a and b are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Lock the two rows and swap positions
        with transaction.atomic():
            a = TeachingAssignment.objects.select_for_update().filter(pk=a_id).first()
            b = TeachingAssignment.objects.select_for_update().filter(pk=b_id).first()
            if not a or not b:
                return Response({"detail": "assignment not found"}, status=status.HTTP_404_NOT_FOUND)
            if a.offering_id != b.offering_id:
                return Response({"detail": "assignments must target the same offering"}, status=status.HTTP_400_BAD_REQUEST)

            a.position, b.position = b.position, a.position
            a.save(update_fields=["position"])
            b.save(update_fields=["position"])

        return Response({"ok": True, "a": a_id, "b": b_id}, status=status.HTTP_200_OK)
