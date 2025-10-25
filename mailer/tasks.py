from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

def _normalize_recipients(recipients):
    if not recipients:
        return []
    if isinstance(recipients, (list, tuple, set)):
        return list(recipients)
    return [str(recipients)]

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_email(self, *, subject, body_text, body_html=None, to, from_email=None, reply_to=None):
    recipients = _normalize_recipients(to)
    if not recipients:
        return {"ok": 0, "to": [], "subject": subject, "ts": timezone.now().isoformat()}

    from_addr = from_email or settings.DEFAULT_FROM_EMAIL
    headers = {}
    if reply_to:
        headers["Reply-To"] = ", ".join(_normalize_recipients(reply_to))

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_addr,
        to=recipients,
        headers=headers or None,
    )
    if body_html:
        msg.attach_alternative(body_html, "text/html")

    with get_connection(
        backend=settings.EMAIL_BACKEND,
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=getattr(settings, "EMAIL_USE_TLS", False),
        use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
        timeout=getattr(settings, "EMAIL_TIMEOUT", 20),
    ) as conn:
        sent = conn.send_messages([msg]) or 0

    return {"ok": sent, "to": recipients, "subject": subject, "ts": timezone.now().isoformat()}

@shared_task
def send_test_email(to=None):
    to_addr = to or settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
    subject = "CampusTimetable • SMTP/Celery test"
    body_text = (
        "Hi!\n\n"
        "Dave you are smelling nice today, ewww! 👃\n\n"
        "This is a background email sent via Celery + Django SMTP.\n"
        "If you're reading this, the pipeline works ✅.\n\n"
        f"From: {settings.DEFAULT_FROM_EMAIL}\n"
        f"Time: {timezone.now().isoformat()}\n"
    )
    body_html = f"""
    <html>
      <body>
        <p>Hi! 👋</p>
        <p>Dave you are smelling nice today, ewww! 👃</p>
        <p>This is a <b>background email</b> sent via <code>Celery</code> + SMTP.</p>
        <p>If you're reading this, the pipeline works ✅.</p>
        <hr/>
        <p><small>From: {settings.DEFAULT_FROM_EMAIL}<br/>
        Time: {timezone.now().isoformat()}</small></p>
      </body>
    </html>
    """
    return send_email.delay(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        to=to_addr,
    )
