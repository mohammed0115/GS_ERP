"""
Management command: zatca_onboard

Usage:
  python manage.py zatca_onboard --org-id 1 --env simulation --otp 123456 \
      --solution-name "GS ERP" --serial 1-ABC-00001 \
      --org-name "شركة الخليج" --unit "الفوترة" --vat 300000000000003
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Onboard an organization with ZATCA (generates key + CSR → Compliance CSID)."

    def add_arguments(self, parser):
        parser.add_argument("--org-id",        type=int, required=True)
        parser.add_argument("--env",            choices=["sandbox", "simulation", "production"], required=True)
        parser.add_argument("--otp",            required=True)
        parser.add_argument("--solution-name",  required=True)
        parser.add_argument("--serial",         required=True)
        parser.add_argument("--org-name",       required=True)
        parser.add_argument("--unit",           required=True)
        parser.add_argument("--vat",            required=True)

    def handle(self, *args, **options):
        from apps.zatca.application.use_cases.onboard_device import OnboardDevice, OnboardDeviceCommand

        cmd = OnboardDeviceCommand(
            organization_id=options["org_id"],
            environment=options["env"],
            otp=options["otp"],
            solution_name=options["solution_name"],
            serial_number=options["serial"],
            organization_name=options["org_name"],
            organizational_unit=options["unit"],
            vat_number=options["vat"],
        )
        try:
            result = OnboardDevice().execute(cmd)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Onboarded successfully.\n"
            f"  credentials_id        : {result.credentials_id}\n"
            f"  compliance_request_id : {result.compliance_request_id}\n"
            f"  message               : {result.message}"
        ))
