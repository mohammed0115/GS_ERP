"""
Alert engine — Phase 7 Sprint 4.

Evaluates active AlertRules and fires AlertEvent records when conditions
are met.  Each alert type has a dedicated evaluator function.

Supported alert types and their condition_json schemas:
  credit_limit_breach     — {"threshold_pct": 90}
  overdue_ar_spike        — {"overdue_days": 30, "min_amount": 0}
  low_liquidity           — {"min_current_ratio": 1.2}
  high_risk_invoice       — {"min_score": 70}
  large_inventory_variance — {"min_variance_pct": 50}
  unreconciled_bank       — (no condition_json needed — fires if unreconciled items exist)
  tax_inconsistency       — {"max_variance_pct": 5}
  period_end_activity     — {"days_before_period_end": 3}
  custom                  — (not evaluated automatically)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Evaluation result
# ---------------------------------------------------------------------------

class AlertFired:
    def __init__(
        self,
        rule,
        source_type: str,
        source_id: int | None,
        message: str,
        context: dict,
    ) -> None:
        self.rule = rule
        self.source_type = source_type
        self.source_id = source_id
        self.message = message
        self.context = context


# ---------------------------------------------------------------------------
# Individual evaluators (one per alert_type)
# ---------------------------------------------------------------------------

def _eval_credit_limit_breach(rule, org_id: int) -> list[AlertFired]:
    from django.db.models import Sum, F
    from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus
    from apps.crm.infrastructure.models import Customer

    threshold_pct = Decimal(str(rule.condition_json.get("threshold_pct", 90))) / Decimal("100")
    results = []

    for customer in Customer.objects.filter(organization_id=org_id):
        credit_limit = getattr(customer, "credit_limit", _ZERO) or _ZERO
        if credit_limit <= _ZERO:
            continue
        outstanding = (
            SalesInvoice.objects.filter(
                organization_id=org_id,
                customer_id=customer.pk,
                status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
            )
            .aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
        ) or _ZERO
        usage = outstanding / credit_limit
        if usage >= threshold_pct:
            results.append(AlertFired(
                rule=rule,
                source_type="crm.customer",
                source_id=customer.pk,
                message=(
                    f"Customer {customer.name} has used {float(usage)*100:.0f}% "
                    f"of their credit limit ({outstanding} / {credit_limit})."
                ),
                context={
                    "outstanding": str(outstanding),
                    "credit_limit": str(credit_limit),
                    "usage_pct": str(round(float(usage) * 100, 1)),
                },
            ))
    return results


def _eval_overdue_ar_spike(rule, org_id: int) -> list[AlertFired]:
    from django.db.models import Sum, F
    from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

    overdue_days = int(rule.condition_json.get("overdue_days", 30))
    min_amount = Decimal(str(rule.condition_json.get("min_amount", 0)))
    today = date.today()
    cutoff = today - timedelta(days=overdue_days)

    overdue_total = (
        SalesInvoice.objects.filter(
            organization_id=org_id,
            status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
            due_date__lt=cutoff,
        )
        .aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
    ) or _ZERO

    if overdue_total >= min_amount and overdue_total > _ZERO:
        return [AlertFired(
            rule=rule,
            source_type="sales.salesinvoice",
            source_id=None,
            message=f"Overdue AR (>{overdue_days} days) reached {overdue_total}.",
            context={"overdue_total": str(overdue_total), "overdue_days": overdue_days},
        )]
    return []


def _eval_low_liquidity(rule, org_id: int) -> list[AlertFired]:
    from django.db.models import Sum
    from apps.finance.infrastructure.models import JournalLine
    from apps.finance.domain.entities import AccountType

    min_ratio = Decimal(str(rule.condition_json.get("min_current_ratio", 1.2)))
    today = date.today()

    def _bs_sum(atype, side, code_prefix):
        return (
            JournalLine.objects.filter(
                entry__organization_id=org_id,
                entry__is_posted=True,
                entry__entry_date__lte=today,
                account__account_type=atype,
                account__code__startswith=code_prefix,
            ).aggregate(v=Sum(side))["v"]
        ) or _ZERO

    cur_assets = _bs_sum(AccountType.ASSET.value, "debit", "1") - _bs_sum(AccountType.ASSET.value, "credit", "1")
    cur_liab   = _bs_sum(AccountType.LIABILITY.value, "credit", "2") - _bs_sum(AccountType.LIABILITY.value, "debit", "2")

    if cur_liab <= _ZERO:
        return []
    ratio = cur_assets / cur_liab
    if ratio < min_ratio:
        return [AlertFired(
            rule=rule,
            source_type="finance.account",
            source_id=None,
            message=f"Current ratio {float(ratio):.2f} is below the threshold {float(min_ratio):.2f}.",
            context={
                "current_ratio": str(round(float(ratio), 4)),
                "current_assets": str(cur_assets),
                "current_liabilities": str(cur_liab),
            },
        )]
    return []


def _eval_high_risk_invoice(rule, org_id: int) -> list[AlertFired]:
    from apps.intelligence.infrastructure.models import RiskScore

    min_score = Decimal(str(rule.condition_json.get("min_score", 70)))
    results = []

    for rs in RiskScore.objects.filter(
        organization_id=org_id,
        entity_type="sales.salesinvoice",
        score__gte=min_score,
    ).order_by("-calculated_at"):
        results.append(AlertFired(
            rule=rule,
            source_type=rs.entity_type,
            source_id=rs.entity_id,
            message=f"Invoice #{rs.entity_id} has risk score {rs.score} [{rs.risk_level}].",
            context={
                "risk_score": str(rs.score),
                "risk_level": rs.risk_level,
                "factors": rs.contributing_factors_json,
            },
        ))
    return results


def _eval_period_end_activity(rule, org_id: int) -> list[AlertFired]:
    from apps.finance.infrastructure.models import JournalEntry
    from apps.finance.infrastructure.fiscal_year_models import AccountingPeriod, PeriodStatus

    days_before = int(rule.condition_json.get("days_before_period_end", 3))
    today = date.today()
    warning_date = today + timedelta(days=days_before)

    try:
        period = AccountingPeriod.objects.filter(
            organization_id=org_id,
            status=PeriodStatus.OPEN,
            end_date__lte=warning_date,
        ).first()
    except Exception:
        return []

    if not period:
        return []

    # Count large-value entries posted in last 3 days
    large_entries = JournalEntry.objects.filter(
        organization_id=org_id,
        is_posted=True,
        entry_date__gte=today - timedelta(days=days_before),
        entry_date__lte=today,
    ).count()

    if large_entries > 0:
        return [AlertFired(
            rule=rule,
            source_type="finance.accountingperiod",
            source_id=period.pk,
            message=(
                f"Period '{period}' closes within {days_before} days. "
                f"{large_entries} entries posted in the final days."
            ),
            context={
                "period_end": str(period.end_date),
                "days_remaining": (period.end_date - today).days,
                "recent_entries": large_entries,
            },
        )]
    return []


def _eval_large_inventory_variance(rule, org_id: int) -> list[AlertFired]:
    from apps.inventory.infrastructure.models import StockCount, StockCountLine, CountStatusChoices

    min_variance_pct = Decimal(str(rule.condition_json.get("min_variance_pct", 50)))
    results = []

    recent_counts = StockCount.objects.filter(
        organization_id=org_id,
        status=CountStatusChoices.FINALISED,
    ).order_by("-count_date")[:20]

    for count in recent_counts:
        for line in StockCountLine.objects.filter(count=count):
            if not line.expected_quantity or line.expected_quantity == _ZERO:
                continue
            variance = abs(line.counted_quantity - line.expected_quantity)
            variance_pct = variance / abs(line.expected_quantity) * Decimal("100")
            if variance_pct < min_variance_pct:
                continue
            results.append(AlertFired(
                rule=rule,
                source_type="inventory.stockcount",
                source_id=count.pk,
                message=(
                    f"Stock count '{count.reference}': product #{line.product_id} "
                    f"variance {float(variance_pct):.0f}% "
                    f"(expected {line.expected_quantity}, counted {line.counted_quantity})."
                ),
                context={
                    "count_reference": count.reference,
                    "product_id": line.product_id,
                    "expected_qty": str(line.expected_quantity),
                    "counted_qty": str(line.counted_quantity),
                    "variance_pct": str(round(float(variance_pct), 1)),
                },
            ))
    return results


def _eval_unreconciled_bank(rule, org_id: int) -> list[AlertFired]:
    from apps.finance.infrastructure.models import JournalEntry

    days_old = int(rule.condition_json.get("days_old", 7))
    cutoff = date.today() - timedelta(days=days_old)

    unposted_count = JournalEntry.objects.filter(
        organization_id=org_id,
        is_posted=False,
        entry_date__lte=cutoff,
    ).count()

    if unposted_count > 0:
        return [AlertFired(
            rule=rule,
            source_type="finance.journalentry",
            source_id=None,
            message=(
                f"{unposted_count} draft journal entr"
                f"{'y' if unposted_count == 1 else 'ies'} unposted "
                f"for more than {days_old} days — bank reconciliation may be incomplete."
            ),
            context={"unposted_count": unposted_count, "days_old": days_old},
        )]
    return []


def _eval_tax_inconsistency(rule, org_id: int) -> list[AlertFired]:
    from django.db.models import Sum
    from apps.finance.infrastructure.tax_models import TaxTransaction
    from apps.finance.infrastructure.models import JournalLine

    max_variance_pct = Decimal(str(rule.condition_json.get("max_variance_pct", 5)))
    today = date.today()
    first_of_month = today.replace(day=1)

    tx_total = (
        TaxTransaction.objects.filter(
            organization_id=org_id,
            direction="output",
            txn_date__gte=first_of_month,
            txn_date__lte=today,
        ).aggregate(v=Sum("tax_amount"))["v"]
    ) or _ZERO

    if tx_total == _ZERO:
        return []

    # GL net credit on liability-type accounts starting with "2" (covers 23xx VAT payable)
    gl_agg = JournalLine.objects.filter(
        entry__organization_id=org_id,
        entry__is_posted=True,
        entry__entry_date__gte=first_of_month,
        entry__entry_date__lte=today,
        account__account_type="liability",
        account__code__startswith="2",
    ).aggregate(credits=Sum("credit"), debits=Sum("debit"))
    gl_tax = (gl_agg["credits"] or _ZERO) - (gl_agg["debits"] or _ZERO)

    if gl_tax == _ZERO:
        return []

    variance = abs(tx_total - gl_tax)
    variance_pct = variance / tx_total * Decimal("100")

    if variance_pct > max_variance_pct:
        return [AlertFired(
            rule=rule,
            source_type="finance.taxtransaction",
            source_id=None,
            message=(
                f"Tax inconsistency: TaxTransaction total {tx_total}, "
                f"GL liability balance {gl_tax} "
                f"({float(variance_pct):.1f}% variance, threshold {float(max_variance_pct):.0f}%)."
            ),
            context={
                "tx_total": str(tx_total),
                "gl_total": str(gl_tax),
                "variance_pct": str(round(float(variance_pct), 2)),
            },
        )]
    return []


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EVALUATORS: dict[str, Callable] = {
    "credit_limit_breach":       _eval_credit_limit_breach,
    "overdue_ar_spike":          _eval_overdue_ar_spike,
    "low_liquidity":             _eval_low_liquidity,
    "high_risk_invoice":         _eval_high_risk_invoice,
    "period_end_activity":       _eval_period_end_activity,
    "large_inventory_variance":  _eval_large_inventory_variance,
    "unreconciled_bank":         _eval_unreconciled_bank,
    "tax_inconsistency":         _eval_tax_inconsistency,
}


# ---------------------------------------------------------------------------
# EvaluateAlertRules use case
# ---------------------------------------------------------------------------

class EvaluateAlertRules:
    """
    Run all active alert rules for an org and fire AlertEvent records.

    Usage::

        count = EvaluateAlertRules().execute(organization_id=org.pk)
    """

    def execute(self, organization_id: int) -> int:
        from django.db import transaction
        from django.utils import timezone
        from apps.intelligence.infrastructure.models import (
            AlertRule, AlertEvent, AlertEventStatus,
        )

        rules = AlertRule.objects.filter(
            organization_id=organization_id,
            is_active=True,
        )

        fired_count = 0
        now = timezone.now()

        for rule in rules:
            evaluator = _EVALUATORS.get(rule.alert_type)
            if not evaluator:
                if rule.alert_type != "custom":
                    logger.warning(
                        "EvaluateAlertRules: no evaluator for alert_type=%r (rule pk=%s) — skipping.",
                        rule.alert_type, rule.pk,
                    )
                continue

            try:
                fired_list = evaluator(rule, organization_id)
            except Exception:
                continue  # never crash the loop for one bad rule

            for fired in fired_list:
                # Deduplicate: skip if same rule+source has an active event
                already_active = AlertEvent.objects.filter(
                    organization_id=organization_id,
                    alert_rule=rule,
                    source_type=fired.source_type,
                    source_id=fired.source_id,
                    status=AlertEventStatus.ACTIVE,
                ).exists()
                if already_active:
                    continue

                with transaction.atomic():
                    AlertEvent.objects.create(
                        organization_id=organization_id,
                        alert_rule=rule,
                        source_type=fired.source_type,
                        source_id=fired.source_id,
                        message=fired.message,
                        severity=rule.severity,
                        status=AlertEventStatus.ACTIVE,
                        triggered_at=now,
                        context_json=fired.context,
                    )
                    fired_count += 1

        return fired_count
