import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from pingu.core.models import CheckResult

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete CheckResult records older than RESULT_RETENTION_DAYS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=f"Override retention days (default: {settings.RESULT_RETENTION_DAYS}).",
        )

    def handle(self, *args, **options):
        days = options["days"] if options["days"] is not None else settings.RESULT_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)

        qs = CheckResult.objects.filter(timestamp__lt=cutoff)
        count = qs.count()

        if count == 0:
            self.stdout.write("No stale results to clean up.")
            return

        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} result(s) older than {days} day(s).")
        )
