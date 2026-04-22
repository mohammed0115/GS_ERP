"""
Audit Case management use cases — Phase 7 Sprint 5.

  OpenAuditCase       — create a new AuditCase (manual or from intelligence signal)
  AssignAuditCase     — assign to a user and move to UNDER_REVIEW
  EscalateAuditCase   — move status to ESCALATED with notes
  CloseAuditCase      — resolve / dismiss / close with outcome
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AuditCaseError(Exception):
    pass


class AuditCaseAlreadyClosedError(AuditCaseError):
    pass


class AuditCaseNotFoundError(AuditCaseError):
    pass


class InvalidAuditCaseTransitionError(AuditCaseError):
    pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpenAuditCaseCommand:
    organization_id: int
    opened_by_id: int | None
    source_type: str
    source_id: int | None
    case_type: str            # AuditCaseType value
    severity: str = "medium"
    signal_type: str = ""
    signal_id: int | None = None


@dataclass(frozen=True)
class AssignAuditCaseCommand:
    organization_id: int
    case_id: int
    assigned_to_id: int


@dataclass(frozen=True)
class EscalateAuditCaseCommand:
    organization_id: int
    case_id: int
    escalation_notes: str


@dataclass(frozen=True)
class CloseAuditCaseCommand:
    organization_id: int
    case_id: int
    final_status: str   # confirmed / dismissed / closed
    outcome: str
    review_notes: str = ""


# ---------------------------------------------------------------------------
# OpenAuditCase
# ---------------------------------------------------------------------------

class OpenAuditCase:

    @transaction.atomic
    def execute(self, cmd: OpenAuditCaseCommand):
        from apps.intelligence.infrastructure.models import AuditCase, AuditCaseStatus

        year = date.today().year

        # Create the record first to obtain a guaranteed-unique PK from the DB,
        # then derive the case_number from it. This eliminates the race condition
        # that would occur if we used count()+1 as a sequence generator.
        case = AuditCase.objects.create(
            organization_id=cmd.organization_id,
            case_number="PENDING",   # temporary — replaced below
            source_type=cmd.source_type,
            source_id=cmd.source_id,
            signal_type=cmd.signal_type,
            signal_id=cmd.signal_id,
            case_type=cmd.case_type,
            severity=cmd.severity,
            status=AuditCaseStatus.OPEN,
            opened_at=timezone.now(),
            opened_by_id=cmd.opened_by_id,
        )
        case_number = f"AC-{year}-{case.pk:04d}"
        AuditCase.objects.filter(pk=case.pk).update(case_number=case_number)
        case.case_number = case_number
        return case


# ---------------------------------------------------------------------------
# AssignAuditCase
# ---------------------------------------------------------------------------

class AssignAuditCase:

    @transaction.atomic
    def execute(self, cmd: AssignAuditCaseCommand):
        from apps.intelligence.infrastructure.models import AuditCase, AuditCaseStatus

        try:
            case = AuditCase.objects.select_for_update().get(
                pk=cmd.case_id,
                organization_id=cmd.organization_id,
            )
        except AuditCase.DoesNotExist:
            raise AuditCaseNotFoundError(f"AuditCase {cmd.case_id} not found.")

        if case.status in (AuditCaseStatus.CLOSED, AuditCaseStatus.DISMISSED):
            raise AuditCaseAlreadyClosedError(
                f"Cannot assign a case with status '{case.status}'."
            )

        case.assigned_to_id = cmd.assigned_to_id
        if case.status == AuditCaseStatus.OPEN:
            case.status = AuditCaseStatus.UNDER_REVIEW
        case.save(update_fields=["assigned_to_id", "status"])
        return case


# ---------------------------------------------------------------------------
# EscalateAuditCase
# ---------------------------------------------------------------------------

class EscalateAuditCase:

    @transaction.atomic
    def execute(self, cmd: EscalateAuditCaseCommand):
        from apps.intelligence.infrastructure.models import AuditCase, AuditCaseStatus

        try:
            case = AuditCase.objects.select_for_update().get(
                pk=cmd.case_id,
                organization_id=cmd.organization_id,
            )
        except AuditCase.DoesNotExist:
            raise AuditCaseNotFoundError(f"AuditCase {cmd.case_id} not found.")

        if case.status in (AuditCaseStatus.CLOSED, AuditCaseStatus.DISMISSED):
            raise AuditCaseAlreadyClosedError(
                f"Cannot escalate a case with status '{case.status}'."
            )

        case.status = AuditCaseStatus.ESCALATED
        case.review_notes = (
            (case.review_notes + "\n" if case.review_notes else "") +
            f"[ESCALATED] {cmd.escalation_notes}"
        )
        case.save(update_fields=["status", "review_notes"])
        return case


# ---------------------------------------------------------------------------
# CloseAuditCase
# ---------------------------------------------------------------------------

class CloseAuditCase:

    TERMINAL_STATUSES = {"closed", "dismissed", "confirmed"}
    ALLOWED_FINAL_STATUSES = {"confirmed", "dismissed", "closed"}

    @transaction.atomic
    def execute(self, cmd: CloseAuditCaseCommand):
        from apps.intelligence.infrastructure.models import AuditCase

        try:
            case = AuditCase.objects.select_for_update().get(
                pk=cmd.case_id,
                organization_id=cmd.organization_id,
            )
        except AuditCase.DoesNotExist:
            raise AuditCaseNotFoundError(f"AuditCase {cmd.case_id} not found.")

        if case.status in self.TERMINAL_STATUSES:
            raise AuditCaseAlreadyClosedError(
                f"Case '{case.case_number}' is already in terminal status '{case.status}'."
            )

        if cmd.final_status not in self.ALLOWED_FINAL_STATUSES:
            raise InvalidAuditCaseTransitionError(
                f"'{cmd.final_status}' is not a valid closing status."
            )

        case.status = cmd.final_status
        case.outcome = cmd.outcome
        if cmd.review_notes:
            case.review_notes = (
                (case.review_notes + "\n" if case.review_notes else "") +
                cmd.review_notes
            )
        case.closed_at = timezone.now()
        case.save(update_fields=["status", "outcome", "review_notes", "closed_at"])
        return case
