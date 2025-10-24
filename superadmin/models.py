# superadmin/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class InstitutionSetting(models.Model):
    """
    Singleton-ish record describing the campus/institution.
    The `singleton` boolean is unique=True to enforce a single row.
    """
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=16, unique=True)  # e.g., CLU
    timezone = models.CharField(max_length=64, default="Africa/Lagos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Institution Setting"
        verbose_name_plural = "Institution Settings"

    def __str__(self):
        return f"{self.name} ({self.code})"


class SuperAdminProfile(models.Model):
    """
    Optional contact/profile fields for the SuperAdmin user.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="superadmin_profile")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "SuperAdmin Profile"
        verbose_name_plural = "SuperAdmin Profiles"

    def __str__(self):
        return f"SuperAdminProfile<{self.user.email}>"


class RecoverySecret(models.Model):
    """
    Stores ONLY HASHES of the one-time Recovery Code and PIN.
    Plain values are returned once by the API; never persisted.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_secrets")
    recovery_code_hash = models.CharField(max_length=255)
    recovery_pin_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Recovery Secret"
        verbose_name_plural = "Recovery Secrets"

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])
