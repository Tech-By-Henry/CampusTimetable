# onboarding/tasks.py
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import IntakeSubmission, ActivationToken, IntakeLink
from mailer.tasks import send_email

User = get_user_model()

@shared_task
def ping():
    return "pong"

@shared_task
def add(x, y):
    return x + y

def _build_activation_url(raw_token: str) -> str:
    base = getattr(settings, "FRONTEND_BASE_URL", "") or ""
    if base:
        if base.endswith("/"):
            base = base[:-1]
        return f"{base}/activate/{raw_token}"
    return f"/api/v1/onboarding/activation/{raw_token}"

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

def _role_strings(role: str):
    """Return human role name + ID label for email copy."""
    if role == IntakeLink.ROLE_STUDENT:
        return "Student", "Matric Number"
    if role == IntakeLink.ROLE_LECTURER:
        return "Lecturer", "Staff ID"
    # default: Admin
    return "Admin", "Staff ID"

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def approve_and_invite(self, *, submission_id: int, approver_id: int | None):
    """
    Background workflow (idempotent):
      - If submission is PENDING -> set APPROVED.
      - If submission is REJECTED -> skip.
      - If not INVITED -> issue/reuse activation token, send email (role-aware), set INVITED.
      - If already INVITED -> skip.
    """
    sub = IntakeSubmission.objects.select_related("link").get(id=submission_id)

    if sub.status == IntakeSubmission.STATUS_REJECTED:
        return {"ok": 0, "skipped": True, "reason": "rejected", "submission_id": sub.id}

    # Approve if still pending (lock to avoid races)
    with transaction.atomic():
        sub = IntakeSubmission.objects.select_for_update().get(id=submission_id)
        if sub.status == IntakeSubmission.STATUS_PENDING:
            sub.status = IntakeSubmission.STATUS_APPROVED
            sub.save(update_fields=["status"])

    if sub.status == IntakeSubmission.STATUS_INVITED:
        return {"ok": 0, "skipped": True, "reason": "already_invited", "submission_id": sub.id}

    ttl = getattr(settings, "ACTIVATION_TTL_HOURS", 72)
    tok, raw_token, reused = ActivationToken.issue_or_reuse(
        submission=sub, created_by_id=approver_id, ttl_hours=ttl
    )

    if reused and not raw_token:
        if sub.status != IntakeSubmission.STATUS_INVITED:
            sub.status = IntakeSubmission.STATUS_INVITED
            sub.emailed_activation_at = sub.emailed_activation_at or timezone.now()
            sub.save(update_fields=["status", "emailed_activation_at"])
        return {"ok": 0, "reused": True, "submission_id": sub.id, "token_id": tok.id}

    activation_url = _build_activation_url(raw_token)
    role_nice, id_label = _role_strings(sub.role)
    ttl_txt = f"{ttl} hour(s)"

    subject = f"Activate your {role_nice} account"
    body_text = (
        f"Hi {sub.first_name},\n\n"
        f"Your {role_nice.lower()} details have been approved. Please complete your account activation.\n\n"
        f"Activation link: {activation_url}\n"
        f"This link will expire in {ttl_txt}.\n\n"
        f"Note: You will need your {id_label} to finish activation.\n\n"
        "If you did not request this, you can ignore this email."
    )
    body_html = f"""
    <html>
      <body>
        <p>Hi {sub.first_name},</p>
        <p>Your <b>{role_nice.lower()}</b> details have been <b>approved</b>. Please complete your account activation.</p>
        <p><a href="{activation_url}">Activate your account</a></p>
        <p>This link will expire in {ttl_txt}.</p>
        <p><small>You will need your <b>{id_label}</b> to finish activation.</small></p>
        <hr/>
        <p style="color:#666;font-size:12px">If you did not request this, you can ignore this email.</p>
      </body>
    </html>
    """

    reply_to = getattr(settings, "EMAIL_REPLY_TO", "") or None
    send_email.delay(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        to=sub.email,
        reply_to=reply_to,
    )

    sub.status = IntakeSubmission.STATUS_INVITED
    sub.emailed_activation_at = timezone.now()
    sub.save(update_fields=["status", "emailed_activation_at"])

    tok.sent_at = timezone.now()
    tok.save(update_fields=["sent_at"])

    return {
        "ok": 1,
        "to": _mask_email(sub.email),
        "submission_id": sub.id,
        "token_id": tok.id,
        "reused": reused,
        "role": sub.role,
    }
