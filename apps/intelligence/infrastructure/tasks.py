"""
Celery periodic tasks for the intelligence app — Phase 7.

  run_anomaly_detection  — daily: scan all orgs for financial anomalies
  evaluate_alert_rules   — hourly: evaluate active alert rules for all orgs
  compute_risk_scores    — nightly: score recent invoices + customers
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


def _active_org_ids() -> list[int]:
    """Return PKs of all active organizations."""
    from apps.tenancy.infrastructure.models import Organization
    return list(
        Organization.objects.filter(is_active=True).values_list("pk", flat=True)
    )


@shared_task(name="intelligence.run_anomaly_detection", bind=True, max_retries=2)
def run_anomaly_detection(self, lookback_days: int = 7) -> dict:
    """
    Run all anomaly detectors for every active organization.

    By default scans the last 7 days. Returns counts per org.
    """
    from apps.intelligence.application.services.anomaly_detection import RunAnomalyDetection

    date_to = date.today()
    date_from = date_to - timedelta(days=lookback_days)
    engine = RunAnomalyDetection()

    results: dict[int, int] = {}
    for org_id in _active_org_ids():
        try:
            count = engine.execute(
                organization_id=org_id,
                date_from=date_from,
                date_to=date_to,
            )
            results[org_id] = count
            if count:
                logger.info("run_anomaly_detection: org=%s new_cases=%s", org_id, count)
        except Exception as exc:
            logger.exception("run_anomaly_detection: org=%s error=%s", org_id, exc)

    total = sum(results.values())
    logger.info("run_anomaly_detection: total_new_cases=%s orgs=%s", total, len(results))
    return {"total_new_cases": total, "by_org": results}


@shared_task(name="intelligence.evaluate_alert_rules", bind=True, max_retries=2)
def evaluate_alert_rules(self) -> dict:
    """
    Evaluate all active alert rules for every active organization.

    Fires AlertEvent records for triggered conditions.
    """
    from apps.intelligence.application.services.alert_engine import EvaluateAlertRules

    engine = EvaluateAlertRules()
    results: dict[int, int] = {}

    for org_id in _active_org_ids():
        try:
            count = engine.execute(organization_id=org_id)
            results[org_id] = count
            if count:
                logger.info("evaluate_alert_rules: org=%s fired=%s", org_id, count)
        except Exception as exc:
            logger.exception("evaluate_alert_rules: org=%s error=%s", org_id, exc)

    total = sum(results.values())
    logger.info("evaluate_alert_rules: total_fired=%s orgs=%s", total, len(results))
    return {"total_fired": total, "by_org": results}


@shared_task(name="intelligence.compute_risk_scores", bind=True, max_retries=2)
def compute_risk_scores(self, lookback_days: int = 30) -> dict:
    """
    Recompute risk scores for recent sales invoices, customers, and purchase invoices.
    """
    from apps.intelligence.application.services.risk_scoring import ComputeRiskScore

    cutoff = date.today() - timedelta(days=lookback_days)
    engine = ComputeRiskScore()
    total_scored = 0

    for org_id in _active_org_ids():
        try:
            from apps.sales.infrastructure.invoice_models import SalesInvoice
            from apps.crm.infrastructure.models import Customer

            # Score recent sales invoices
            invoice_ids = list(
                SalesInvoice.objects.filter(
                    organization_id=org_id,
                    invoice_date__gte=cutoff,
                ).values_list("pk", flat=True)[:500]
            )
            for inv_id in invoice_ids:
                try:
                    engine.execute(
                        organization_id=org_id,
                        entity_type="sales.salesinvoice",
                        entity_id=inv_id,
                    )
                    total_scored += 1
                except Exception:
                    pass

            # Score customers with recent invoice activity
            customer_ids = list(
                SalesInvoice.objects.filter(
                    organization_id=org_id,
                    invoice_date__gte=cutoff,
                ).values_list("customer_id", flat=True).distinct()[:200]
            )
            for cust_id in customer_ids:
                try:
                    engine.execute(
                        organization_id=org_id,
                        entity_type="crm.customer",
                        entity_id=cust_id,
                    )
                    total_scored += 1
                except Exception:
                    pass

        except Exception as exc:
            logger.exception("compute_risk_scores: org=%s error=%s", org_id, exc)

        # Score recent purchase invoices
        try:
            from apps.purchases.infrastructure.payable_models import PurchaseInvoice
            pinv_ids = list(
                PurchaseInvoice.objects.filter(
                    organization_id=org_id,
                    invoice_date__gte=cutoff,
                ).values_list("pk", flat=True)[:500]
            )
            for inv_id in pinv_ids:
                try:
                    engine.execute(
                        organization_id=org_id,
                        entity_type="purchases.purchaseinvoice",
                        entity_id=inv_id,
                    )
                    total_scored += 1
                except Exception:
                    pass
        except Exception as exc:
            logger.exception("compute_risk_scores (purchases): org=%s error=%s", org_id, exc)

    logger.info("compute_risk_scores: total_scored=%s", total_scored)
    return {"total_scored": total_scored}


@shared_task(name="intelligence.compute_kpis", bind=True, max_retries=2)
def compute_kpis(self) -> dict:
    """
    Compute the 9 financial KPIs for every active organization.

    Covers the current month (month-to-date) against the prior month.
    Runs nightly so executive dashboards always reflect fresh data.
    """
    from apps.intelligence.application.use_cases.compute_kpis import (
        ComputeKPIs, ComputeKPIsCommand,
    )

    today = date.today()
    period_start = today.replace(day=1)
    period_end = today

    # Prior month
    prior_end = period_start - timedelta(days=1)
    prior_start = prior_end.replace(day=1)

    engine = ComputeKPIs()
    total_kpis = 0

    org_ids = _active_org_ids()
    for org_id in org_ids:
        try:
            result = engine.execute(ComputeKPIsCommand(
                organization_id=org_id,
                period_start=period_start,
                period_end=period_end,
                prior_start=prior_start,
                prior_end=prior_end,
            ))
            total_kpis += len(result.kpis)
            logger.info("compute_kpis: org=%s kpis=%s", org_id, len(result.kpis))
        except Exception as exc:
            logger.exception("compute_kpis: org=%s error=%s", org_id, exc)

    logger.info("compute_kpis: total_kpis=%s orgs=%s", total_kpis, len(org_ids))
    return {"total_kpis": total_kpis}
