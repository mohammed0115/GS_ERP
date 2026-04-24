"""
CRM signals.

- Auto-assign default TaxProfile to new Customer/Supplier based on org tax_system.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_signals() -> None:
    from django.db.models.signals import post_save
    from apps.crm.infrastructure.models import Customer, Supplier

    post_save.connect(_auto_tax_profile_customer, sender=Customer)
    post_save.connect(_auto_tax_profile_supplier, sender=Supplier)
    logger.debug("CRM: auto tax_profile signals registered.")


def _auto_tax_profile_customer(sender, instance, created: bool, **kwargs) -> None:
    if not created or instance.tax_profile_id:
        return
    _assign_default_tax_profile(instance)


def _auto_tax_profile_supplier(sender, instance, created: bool, **kwargs) -> None:
    if not created or instance.tax_profile_id:
        return
    _assign_default_tax_profile(instance)


def _assign_default_tax_profile(instance) -> None:
    """
    Look up the org's tax_system and assign the matching default TaxProfile.

    Matching logic (by code convention):
      sa_vat       → TaxProfile with code "DEFAULT-VAT" or "VAT15"
      us_sales_tax → TaxProfile with code "DEFAULT-SALES-TAX" or "US-EXEMPT"
    Falls back silently if no matching profile exists.
    """
    try:
        from apps.tenancy.infrastructure.models import Organization
        from apps.finance.infrastructure.tax_models import TaxProfile

        org = Organization.objects.filter(pk=instance.organization_id).values("tax_system").first()
        if not org or not org["tax_system"]:
            return

        tax_system = org["tax_system"]
        code_candidates = {
            "sa_vat":       ["DEFAULT-VAT", "VAT15", "VAT-15"],
            "us_sales_tax": ["DEFAULT-SALES-TAX", "US-TAX", "SALES-TAX"],
        }.get(tax_system, [])

        for code in code_candidates:
            profile = TaxProfile.objects.filter(
                organization_id=instance.organization_id,
                code=code,
                is_active=True,
            ).first()
            if profile:
                type(instance).objects.filter(pk=instance.pk).update(tax_profile=profile)
                logger.debug(
                    "CRM: auto-assigned TaxProfile '%s' to %s pk=%s",
                    code, type(instance).__name__, instance.pk,
                )
                return
    except Exception:
        logger.exception("CRM: error in _assign_default_tax_profile for %s pk=%s",
                         type(instance).__name__, instance.pk)
