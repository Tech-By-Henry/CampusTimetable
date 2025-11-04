# lecturers/views/BlackoutRequest.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from ..serializers.BlackoutRequest import LecturerBlackoutRequestSerializer
from ..models import LecturerBlackoutRequest
from ..permissions import IsLecturerUser

class LecturerBlackoutRequestViewSet(viewsets.ModelViewSet):
    """
    Lecturer-side Blackout Request endpoints (lecturer-level).
    - List / Retrieve / Create
    - Withdraw (cancel) pending requests
    """
    serializer_class = LecturerBlackoutRequestSerializer
    permission_classes = [IsAuthenticated, IsLecturerUser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        # lecturers only see their own requests
        user = self.request.user
        qs = LecturerBlackoutRequest.objects.select_related(
            "lecturer", "term", "slot", "reschedule_entry", "reviewed_by"
        ).filter(lecturer_id=user.id)
        status_q = self.request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q.upper())
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        # force lecturer to be current user
        serializer.save(lecturer=self.request.user)

    @action(detail=True, methods=["post"], url_path="withdraw")
    def withdraw(self, request, pk=None):
        """
        Withdraw (cancel) a pending blackout request.
        Only allowed for the requesting lecturer and only when status == PENDING.
        """
        obj = get_object_or_404(LecturerBlackoutRequest, pk=pk)
        if obj.lecturer_id != request.user.id:
            raise PermissionDenied("You can only withdraw your own requests.")

        if obj.status != LecturerBlackoutRequest.STATUS_PENDING:
            return Response({"detail": "Only pending requests can be withdrawn."}, status=status.HTTP_400_BAD_REQUEST)

        obj.status = LecturerBlackoutRequest.STATUS_CANCELLED
        obj.save(update_fields=["status", "updated_at"])
        return Response({"ok": True, "status": obj.status}, status=status.HTTP_200_OK)
