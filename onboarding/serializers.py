# onboarding/serializers.py
from rest_framework import serializers
from .models import IntakeLink, IntakeSubmission

class IntakeLinkCreateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[c[0] for c in IntakeLink.ROLE_CHOICES])

    def create(self, validated_data):
        user = self.context["request"].user
        return IntakeLink.create_unique(role=validated_data["role"], user=user, ttl_hours=24)


class IntakeLinkResponseSerializer(serializers.ModelSerializer):
    public_path = serializers.SerializerMethodField()
    expired = serializers.SerializerMethodField()

    class Meta:
        model = IntakeLink
        fields = ("id", "role", "token", "public_path", "expires_at", "is_active", "created_at", "expired")

    def get_public_path(self, obj: IntakeLink) -> str:
        return f"/intake/{obj.token}"

    def get_expired(self, obj: IntakeLink) -> bool:
        return obj.is_expired


class IntakeSubmitSerializer(serializers.Serializer):
    """
    Public submit: depending on link.role, we accept either matric_no (student) or staff_id (admin/lecturer).
    """
    first_name = serializers.CharField(max_length=100)
    last_name  = serializers.CharField(max_length=100)
    email      = serializers.EmailField()

    # Optional fields; we validate presence based on role:
    matric_no = serializers.CharField(max_length=64, required=False, allow_blank=False)
    staff_id  = serializers.CharField(max_length=64, required=False, allow_blank=False)

    def validate(self, attrs):
        link: IntakeLink = self.context["link"]
        # Pick the correct ID field based on role
        if link.role == IntakeLink.ROLE_STUDENT:
            idv = attrs.get("matric_no")
            if not idv:
                raise serializers.ValidationError({"matric_no": "Matric number is required."})
        else:
            idv = attrs.get("staff_id")
            if not idv:
                raise serializers.ValidationError({"staff_id": "Staff ID is required."})

        # Normalize ID code: uppercase + strip surrounding spaces
        id_code = str(idv).strip().upper()
        attrs["id_code"] = id_code

        # Dedupe per link/id_code
        if IntakeSubmission.objects.filter(link=link, id_code=id_code).exists():
            raise serializers.ValidationError("A submission already exists for this ID on this link.")

        return attrs

    def create(self, validated):
        request = self.context["request"]
        link: IntakeLink = self.context["link"]

        client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",", 1)[0].strip()
        if not client_ip:
            client_ip = request.META.get("REMOTE_ADDR", "") or ""

        sub = IntakeSubmission.objects.create(
            link=link,
            role=link.role,
            id_code=validated["id_code"],
            first_name=validated["first_name"],
            last_name=validated["last_name"],
            email=validated["email"],
            client_ip=client_ip[:45],
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1024],
        )
        return sub


# -------- Admin/InstitutionOwner management --------

class IntakeSubmissionListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntakeSubmission
        fields = ("id", "role", "id_code", "first_name", "last_name", "email", "status", "created_at")


class IntakeBulkReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("APPROVE", "REJECT"))
    submission_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)

    def validate(self, attrs):
        link: IntakeLink = self.context["link"]
        ids = list(dict.fromkeys(attrs["submission_ids"]))  # de-dup while keeping order
        qs = IntakeSubmission.objects.filter(link=link, id__in=ids)

        found_ids = set(qs.values_list("id", flat=True))
        missing = [i for i in ids if i not in found_ids]
        if missing:
            raise serializers.ValidationError({"submission_ids": f"Not found for this link: {missing}"})

        attrs["ids"] = ids
        attrs["qs"] = qs
        return attrs

    def save(self, **kwargs):
        from .tasks import approve_and_invite  # local import to avoid cycles

        request = self.context.get("request")
        action = self.validated_data["action"]
        ids = self.validated_data["ids"]
        qs = self.validated_data["qs"]

        if action == "REJECT":
            # Synchronous small update is ok for REJECT (no email flow)
            pending_qs = qs.filter(status=IntakeSubmission.STATUS_PENDING)
            updated = pending_qs.update(status=IntakeSubmission.STATUS_REJECTED)
            skipped = [i for i in ids if i not in set(pending_qs.values_list("id", flat=True))]
            return {"updated": updated, "skipped": skipped, "action": action, "ids": ids}

        # APPROVE: queue background jobs — Celery will approve + email + mark invited
        approver_id = (request.user.id if request and getattr(request, "user", None) and request.user.is_authenticated else None)
        queued = 0
        for sid in ids:
            approve_and_invite.delay(submission_id=sid, approver_id=approver_id)
            queued += 1

        # We return queued count (using 'updated' for backward compatibility)
        return {"updated": queued, "skipped": [], "action": action, "ids": ids}

