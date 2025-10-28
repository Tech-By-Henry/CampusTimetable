from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from onboarding.models import IntakeSubmission, IntakeLink
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.serializers.lecturers import LecturerRosterItemSerializer

class AdminLecturersViewSet(viewsets.ViewSet):
    """
    Read-only roster of lecturers visible to admins.
    GET /api/v1/admin/lecturers/?status=INVITED|APPROVED|ACTIVATED&activated_only=1&q=smith
    """
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]

    def list(self, request):
        qs = IntakeSubmission.objects.select_related("user").filter(role=IntakeLink.ROLE_LECTURER)
        status_param   = request.query_params.get("status")
        activated_only = request.query_params.get("activated_only")
        q              = request.query_params.get("q")

        if status_param:
            qs = qs.filter(status=status_param)
        if activated_only in ("1", "true", "True"):
            qs = qs.filter(activated_at__isnull=False, user__isnull=False)
        if q:
            qs = qs.filter(
                Q(email__icontains=q) | Q(id_code__icontains=q) |
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )

        results = []
        for s in qs.order_by("-created_at")[:500]:
            results.append({
                "id": s.id,
                "id_code": s.id_code,
                "email": s.email,
                "name": f"{s.first_name} {s.last_name}".strip(),
                "status": s.status,
                "activated": bool(s.activated_at),
            })
        ser = LecturerRosterItemSerializer(results, many=True)
        return Response({"count": len(results), "results": ser.data}, status=status.HTTP_200_OK)

    @classmethod
    def _activated_payload(cls, s):
        return {
            "user_id": s.user_id,
            "email": s.email,
            "id_code": s.id_code,
            "name": f"{s.first_name} {s.last_name}".strip(),
        }

    def activated_users(self, request):
        # not used; declared via @action below
        pass

    from rest_framework.decorators import action  # keep local import to avoid clutter
    @action(detail=False, methods=["get"], url_path="activated-users")
    def activated_users_action(self, request):
        qs = IntakeSubmission.objects.select_related("user").filter(
            role=IntakeLink.ROLE_LECTURER, activated_at__isnull=False, user__isnull=False
        ).order_by("email")
        results = [self._activated_payload(s) for s in qs]
        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)
