import asyncio
import logging

from django.core.management.base import BaseCommand

from pingu.core.services import evaluate_check_result, execute_checks, get_checks_due

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run all due uptime checks."

    def handle(self, *args, **options):
        checks = get_checks_due()
        if not checks:
            self.stdout.write("No checks due.")
            return

        self.stdout.write(f"Running {len(checks)} check(s)...")

        results = asyncio.run(execute_checks(checks))

        saved = 0
        for result in results:
            try:
                result.save()
                evaluate_check_result(result)
                saved += 1
            except Exception:
                logger.exception(
                    "Error saving/evaluating result for check %s",
                    result.check.name,
                )

        self.stdout.write(self.style.SUCCESS(f"Completed: {saved}/{len(results)} results saved."))
