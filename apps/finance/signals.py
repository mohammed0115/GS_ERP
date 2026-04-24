"""
Finance app signals.

- JournalEntry immutability: blocks any field update on a posted entry.
  Corrections must go through the ReverseJournalEntry use case.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_signals() -> None:
    from django.db.models.signals import pre_save
    from apps.finance.infrastructure.models import JournalEntry, JournalLine

    pre_save.connect(_guard_posted_journal_entry, sender=JournalEntry)
    pre_save.connect(_compute_functional_amounts, sender=JournalLine)
    logger.debug("Finance signals registered.")


def _compute_functional_amounts(sender, instance, **kwargs) -> None:
    """Auto-compute functional_debit / functional_credit from exchange_rate."""
    from decimal import Decimal, ROUND_HALF_UP
    rate = instance.exchange_rate or Decimal("1")
    instance.functional_debit = (instance.debit * rate).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    instance.functional_credit = (instance.credit * rate).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def _guard_posted_journal_entry(sender, instance, **kwargs) -> None:
    """Raise if anyone tries to update a posted JournalEntry."""
    if not instance.pk:
        return  # new record — allow
    try:
        current = sender.objects.filter(pk=instance.pk).values("is_posted").first()
    except Exception:
        return
    if current and current["is_posted"]:
        from django.core.exceptions import ValidationError
        raise ValidationError(
            f"JournalEntry {instance.pk} is posted and immutable. "
            "Use ReverseJournalEntry to correct it."
        )
