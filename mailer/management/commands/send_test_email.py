from django.core.management.base import BaseCommand
from mailer.tasks import send_test_email

class Command(BaseCommand):
    help = "Queue a background test email via Celery."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            default=None,
            help="Recipient email address (defaults to DEFAULT_FROM_EMAIL).",
        )

    def handle(self, *args, **opts):
        to = opts["to"]
        result = send_test_email.delay(to=to)
        self.stdout.write(self.style.SUCCESS(f"Queued send_test_email task: {result.id}"))
