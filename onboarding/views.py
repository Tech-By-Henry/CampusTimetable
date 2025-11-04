# onboarding/views.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from rest_framework import permissions, throttling, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import IntakeLink, IntakeSubmission, ActivationToken
from .serializers import (
    IntakeLinkCreateSerializer,
    IntakeLinkResponseSerializer,
    IntakeSubmitSerializer,
    IntakeSubmissionListItemSerializer,
    IntakeBulkReviewSerializer,
)

User = get_user_model()


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class PublicSubmitThrottle(throttling.AnonRateThrottle):
    rate = "10/min"


def _can_manage_link(user, link: IntakeLink) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return link.created_by_id == user.id


class OnboardingViewSet(viewsets.ViewSet):
    """Router-backed endpoints for onboarding."""

    # ---------- Create intake link ----------
    @action(detail=False, methods=["post"], url_path=r"intake-links", permission_classes=[permissions.IsAuthenticated])
    def create_intake_link(self, request):
        role = (request.data.get("role") or "").strip().upper()   # <-- normalize

        if request.user.is_superuser:
            allowed = {IntakeLink.ROLE_ADMIN, IntakeLink.ROLE_LECTURER, IntakeLink.ROLE_STUDENT}
        elif request.user.is_staff:
            allowed = {IntakeLink.ROLE_LECTURER, IntakeLink.ROLE_STUDENT}
        else:
            allowed = {IntakeLink.ROLE_STUDENT}

        if role not in allowed:
            return Response(
                {"detail": f"You are not permitted to create links for role={role}."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = IntakeLinkCreateSerializer(data={"role": role}, context={"request": request})
        ser.is_valid(raise_exception=True)
        link = ser.save()
        return Response(IntakeLinkResponseSerializer(link).data, status=status.HTTP_201_CREATED)


    # ---------- Public: link info + submit ----------
    @action(detail=False, methods=["get"], url_path=r"intake/(?P<token>[^/]+)", permission_classes=[permissions.AllowAny])
    def intake_info(self, request, token: str):
        link = get_object_or_404(IntakeLink, token=token)
        data = IntakeLinkResponseSerializer(link).data
        if not link.is_active or link.is_expired:
            return Response(data | {"detail": "Link is inactive or expired."}, status=status.HTTP_410_GONE)
        return Response(data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path=r"intake/(?P<token>[^/]+)/submit",
        permission_classes=[permissions.AllowAny],
        throttle_classes=[PublicSubmitThrottle],
    )
    def intake_submit(self, request, token: str):
        link = get_object_or_404(IntakeLink, token=token)
        if not link.is_active or link.is_expired:
            return Response({"detail": "This link is inactive or has expired."}, status=status.HTTP_410_GONE)
        ser = IntakeSubmitSerializer(data=request.data, context={"request": request, "link": link})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        sub = ser.save()
        return Response(
            {"ok": True, "submission_id": sub.id, "message": "Submission received. You’ll be notified after review."},
            status=status.HTTP_201_CREATED,
        )

    # ---------- Management: per-link submissions ----------
    @action(detail=False, methods=["get"], url_path=r"intake/(?P<link_id>\d+)/submissions", permission_classes=[permissions.IsAuthenticated])
    def list_submissions(self, request, link_id: int):
        link = get_object_or_404(IntakeLink, id=link_id)
        if not _can_manage_link(request.user, link):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get("status")
        role_filter = request.query_params.get("role")

        qs = link.submissions.all().order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if role_filter:
            qs = qs.filter(role=role_filter)

        data = IntakeSubmissionListItemSerializer(qs, many=True).data
        return Response({"link": {"id": link.id, "role": link.role}, "count": len(data), "results": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path=r"intake/(?P<link_id>\d+)/review", permission_classes=[permissions.IsAuthenticated])
    def bulk_review(self, request, link_id: int):
        link = get_object_or_404(IntakeLink, id=link_id)
        if not _can_manage_link(request.user, link):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        ser = IntakeBulkReviewSerializer(data=request.data, context={"link": link, "request": request})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        outcome = ser.save()
        return Response({"ok": True, "link_id": link.id, **outcome}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path=r"intake/(?P<link_id>\d+)/approve-all", permission_classes=[permissions.IsAuthenticated])
    def approve_all(self, request, link_id: int):
        from .tasks import approve_and_invite
        link = get_object_or_404(IntakeLink, id=link_id)
        if not _can_manage_link(request.user, link):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        pending_ids = list(link.submissions.filter(status=IntakeSubmission.STATUS_PENDING).values_list("id", flat=True))
        approver_id = request.user.id
        for sid in pending_ids:
            approve_and_invite.delay(submission_id=sid, approver_id=approver_id)
        return Response(
            {"ok": True, "link_id": link.id, "role": link.role, "queued": len(pending_ids), "message": f"Queued {len(pending_ids)} submission(s) for approval + invite."},
            status=status.HTTP_200_OK,
        )

    # ---------- NEW: Global listings (role-segmented) ----------
    def _visible_submissions_qs(self, request):
        qs = IntakeSubmission.objects.select_related("link").all().order_by("-created_at")
        if not request.user.is_superuser:
            qs = qs.filter(link__created_by_id=request.user.id)
        # optional query params for all global listings
        status_filter = request.query_params.get("status")
        role_filter = request.query_params.get("role")
        link_id = request.query_params.get("link_id")
        q = request.query_params.get("q")  # search by email or id_code

        if status_filter:
            qs = qs.filter(status=status_filter)
        if role_filter:
            qs = qs.filter(role=role_filter)
        if link_id:
            qs = qs.filter(link_id=link_id)
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(id_code__icontains=q))
        return qs

    @action(detail=False, methods=["get"], url_path=r"submissions", permission_classes=[permissions.IsAuthenticated])
    def submissions_all(self, request):
        qs = self._visible_submissions_qs(request)
        data = IntakeSubmissionListItemSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"submissions/students", permission_classes=[permissions.IsAuthenticated])
    def submissions_students(self, request):
        request._request.GET._mutable = True  # allow injecting param for reuse
        request.query_params._mutable = True
        request.query_params["role"] = IntakeLink.ROLE_STUDENT
        request.query_params._mutable = False
        qs = self._visible_submissions_qs(request)
        data = IntakeSubmissionListItemSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"submissions/lecturers", permission_classes=[permissions.IsAuthenticated])
    def submissions_lecturers(self, request):
        request._request.GET._mutable = True
        request.query_params._mutable = True
        request.query_params["role"] = IntakeLink.ROLE_LECTURER
        request.query_params._mutable = False
        qs = self._visible_submissions_qs(request)
        data = IntakeSubmissionListItemSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"submissions/admins", permission_classes=[permissions.IsAuthenticated])
    def submissions_admins(self, request):
        request._request.GET._mutable = True
        request.query_params._mutable = True
        request.query_params["role"] = IntakeLink.ROLE_ADMIN
        request.query_params._mutable = False
        qs = self._visible_submissions_qs(request)
        data = IntakeSubmissionListItemSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    # ---------- Activation ----------
    @action(detail=False, methods=["get"], url_path=r"activation/(?P<token>[^/]+)", permission_classes=[permissions.AllowAny])
    def activation_info(self, request, token: str):
        tok = ActivationToken.from_raw_token(token)
        if not tok:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_404_NOT_FOUND)
        if not tok.is_active:
            return Response({"detail": "Token is no longer valid."}, status=status.HTTP_410_GONE)
        sub = tok.submission
        payload = {
            "ok": True,
            "role": sub.role,
            "email_masked": self._mask_email(sub.email),
            "expires_at": tok.expires_at,
            "requires": ["id_code", "password", "confirm_password"],
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path=r"activation/(?P<token>[^/]+)/complete", permission_classes=[permissions.AllowAny])
    def activation_complete(self, request, token: str):
        tok = ActivationToken.from_raw_token(token)
        if not tok:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_404_NOT_FOUND)
        if not tok.is_active:
            return Response({"detail": "Token is no longer valid."}, status=status.HTTP_410_GONE)
        sub = tok.submission
        id_code = (request.data.get("id_code") or "").strip().upper()
        pwd = request.data.get("password") or ""
        pwd2 = request.data.get("confirm_password") or ""
        if not id_code or not pwd or not pwd2:
            return Response({"detail": "id_code, password and confirm_password are required."}, status=status.HTTP_400_BAD_REQUEST)
        if pwd != pwd2:
            return Response({"detail": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)
        if id_code != sub.id_code:
            return Response({"detail": "ID code does not match."}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=sub.email,
            defaults={
                "username": sub.email,
                "first_name": sub.first_name,
                "last_name": sub.last_name,
                "is_active": True,
            },
        )
        if not created:
            changed = False
            if not user.first_name and sub.first_name:
                user.first_name = sub.first_name
                changed = True
            if not user.last_name and sub.last_name:
                user.last_name = sub.last_name
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                user.save(update_fields=["first_name", "last_name", "is_active"])

        # Set password
        user.set_password(pwd)
        user.save()

        # Role-based privilege on activation
        if sub.role == IntakeLink.ROLE_ADMIN and not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])

        # Link submission to user and mark consumed
        sub.user = user
        sub.activated_at = timezone.now()
        sub.save(update_fields=["user", "activated_at"])

        tok.consumed_at = timezone.now()
        tok.save(update_fields=["consumed_at"])

        return Response({"ok": True, "message": "Account activated."}, status=status.HTTP_200_OK)

    # helpers
    @staticmethod
    def _mask_email(email: str) -> str:
        try:
            local, domain = email.split("@", 1)
        except ValueError:
            return email
        if len(local) <= 2:
            local_mask = local[0] + "*"
        else:
            local_mask = local[:2] + "*" * (len(local) - 2)
        return f"{local_mask}@{domain}"

