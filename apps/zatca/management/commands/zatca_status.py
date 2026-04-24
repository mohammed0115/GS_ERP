"""
Management command: zatca_status

Print a summary of ZATCA submission statuses for an organization.

Usage:
  python manage.py zatca_status --org-id 1
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print ZATCA submission status summary for an organization."

    def add_arguments(self, parser):
        parser.add_argument("--org-id", type=int, required=True)

    def handle(self, *args, **options):
        from django.db.models import Count
        from apps.zatca.infrastructure.models import ZATCAInvoice, ZATCACredentials

        org_id = options["org_id"]

        # Credentials
        creds = ZATCACredentials.objects.filter(organization_id=org_id)
        self.stdout.write("── Credentials ──────────────────────────────")
        if creds.exists():
            for c in creds:
                active = "✓ active" if c.is_active else "✗ inactive"
                self.stdout.write(f"  [{c.environment}] {active}  expires={c.expires_at}")
        else:
            self.stdout.write("  No credentials found.")

        # Invoice counts by status
        self.stdout.write("\n── Invoice Submission Status ─────────────────")
        rows = (
            ZATCAInvoice.objects.filter(organization_id=org_id)
            .values("status")
            .annotate(n=Count("id"))
            .order_by("status")
        )
        if rows:
            for row in rows:
                self.stdout.write(f"  {row['status']:12s}  {row['n']}")
        else:
            self.stdout.write("  No ZATCA invoices yet.")
