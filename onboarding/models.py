from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta
import base64
import secrets
import hashlib

# --- Token: URL-safe Base64 (no '=') ---
def _gen_token_b64url(nbytes: int = 36) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode("ascii").rstrip("=")

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

class IntakeLink(models.Model):
    ROLE_ADMIN = "ADMIN"
    ROLE_LECTURER = "LECTURER"
    ROLE_STUDENT = "STUDENT"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_LECTURER, "Lecturer"),
        (ROLE_STUDENT, "Student"),
    ]

    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="intake_links"
    )
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.role} link {self.token[:8]}… (active={self.is_active})"

    @classmethod
    def create_unique(cls, *, role: str, user, ttl_hours: int = 24):
        # Generate a unique ~48-char base64url token
        for _ in range(10):
            token = _gen_token_b64url(36)
            if not cls.objects.filter(token=token).exists():
                break
        else:
            raise RuntimeError("Failed to generate unique token")
        return cls.objects.create(
            token=token,
            role=role,
            created_by=user,
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
            is_active=True,
        )

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class IntakeSubmission(models.Model):
    """
    Public self-submission lands here (CSV-in-the-cloud).
    We dedupe by (link, id_code) to avoid spam/duplicates.
    """
    STATUS_PENDING = "PENDING"
    STATUS_REJECTED = "REJECTED"
    STATUS_APPROVED = "APPROVED"
    STATUS_INVITED = "INVITED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_INVITED, "Invited"),
    ]

    link = models.ForeignKey(IntakeLink, on_delete=models.CASCADE, related_name="submissions")
    role = models.CharField(max_length=16, choices=IntakeLink.ROLE_CHOICES)

    # One official identifier, normalized to uppercase without surrounding spaces.
    id_code = models.CharField(max_length=64, db_index=True)

    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    email      = models.EmailField()

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    client_ip  = models.CharField(max_length=45, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")

    # NEW: activation lifecycle
    emailed_activation_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["link", "id_code"], name="uniq_submission_per_link_id"),
        ]

    def __str__(self):
        return f"{self.role}:{self.id_code} [{self.status}] via {self.link_id}"


class ActivationToken(models.Model):
    PURPOSE_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"
    PURPOSE_CHOICES = [
        (PURPOSE_ACCOUNT_ACTIVATION, "Account Activation"),
    ]

    submission = models.ForeignKey(IntakeSubmission, on_delete=models.CASCADE, related_name="activation_tokens")
    email = models.EmailField()  # snapshot for sanity
    purpose = models.CharField(max_length=64, choices=PURPOSE_CHOICES)
    token_hash = models.CharField(max_length=64, db_index=True)  # sha256 hex
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["submission", "purpose"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"ActivationToken<{self.purpose} sub={self.submission_id} exp={self.expires_at.isoformat()}>"

    @property
    def is_active(self) -> bool:
        now = timezone.now()
        return (self.consumed_at is None) and (self.revoked_at is None) and (self.expires_at > now)

    @classmethod
    def issue_or_reuse(
        cls,
        *,
        submission: IntakeSubmission,
        created_by_id: int | None = None,
        created_by=None,
        ttl_hours: int,
    ) -> tuple["ActivationToken", str | None, bool]:
        """
        Returns (token_obj, raw_token, reused_flag).
        If an active token exists, reuse it (idempotent). Otherwise, mint a fresh one.

        Accepts either created_by_id or created_by (User or None).
        """
        now = timezone.now()
        existing = (
            cls.objects.filter(
                submission=submission,
                purpose=cls.PURPOSE_ACCOUNT_ACTIVATION,
                consumed_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            return existing, None, True

        raw = _gen_token_b64url(32)  # ~43 chars
        create_kwargs = dict(
            submission=submission,
            email=submission.email,
            purpose=cls.PURPOSE_ACCOUNT_ACTIVATION,
            token_hash=_sha256_hex(raw),
            expires_at=now + timedelta(hours=ttl_hours),
        )
        if created_by_id is not None:
            create_kwargs["created_by_id"] = created_by_id
        elif created_by is not None:
            create_kwargs["created_by"] = created_by

        tok = cls.objects.create(**create_kwargs)
        return tok, raw, False

    @classmethod
    def from_raw_token(cls, raw_token: str):
        h = _sha256_hex(raw_token)
        return cls.objects.filter(token_hash=h).select_related("submission", "submission__link").first()
