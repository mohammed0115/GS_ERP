"""
Management command: zatca_resubmit

Re-queue failed/pending ZATCA invoices for an organization.

Usage:
  python manage.py zatca_resubmit --org-id 1
  python manage.py zatca_resubmit --org-id 1 --status error rejected
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Re-queue failed/pending ZATCA invoices for submission."

    def add_arguments(self, parser):
        parser.add_argument("--org-id", type=int, required=True)
        parser.add_argument(
            "--status",
            nargs="+",
            default=["error", "pending", "rejected"],
            help="Submission statuses to requeue (default: error pending rejected).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from apps.zatca.infrastructure.models import ZATCAInvoice
        from apps.zatca.tasks import submit_invoice_to_zatca

        qs = ZATCAInvoice.objects.filter(
            organization_id=options["org_id"],
            status__in=options["status"],
        )
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"[dry-run] Would re-queue {count} invoice(s).")
            return

        queued = 0
        for zi in qs:
            submit_invoice_to_zatca.delay(zi.pk, zi.organization_id)
            queued += 1

        self.stdout.write(self.style.SUCCESS(f"Queued {queued} invoice(s) for re-submission."))
