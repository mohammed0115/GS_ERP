"""
Phase-3 DB constraint hardening.

New constraints:
  PurchaseInvoice    — allocated_amount ≤ grand_total, exchange_rate > 0,
                       withholding_tax_percent ∈ [0,100], withholding_tax_amount ≥ 0
  VendorPayment      — allocated_amount ≤ amount, exchange_rate > 0,
                       withholding_tax_percent ∈ [0,100],
                       withholding_tax_amount ≤ amount,
                       (withholding_tax_amount > 0) ⇒ withholding_tax_account IS NOT NULL
  PurchaseInvoiceLine — tax_amount ≥ 0, discount_amount ≥ 0
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0010_vendorpayment_treasury_bank_account"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # PurchaseInvoice                                                     #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__lte=models.F("grand_total")),
                name="purchases_pinv_allocated_not_exceeds_total",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="purchases_pinv_exchange_rate_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(withholding_tax_percent__gte=0)
                    & models.Q(withholding_tax_percent__lte=100)
                ),
                name="purchases_pinv_wht_percent_in_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(withholding_tax_amount__gte=0),
                name="purchases_pinv_wht_amount_non_negative",
            ),
        ),
        # ------------------------------------------------------------------ #
        # VendorPayment                                                       #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__lte=models.F("amount")),
                name="purchases_vpay_allocated_not_exceeds_amount",
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="purchases_vpay_exchange_rate_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(withholding_tax_percent__gte=0)
                    & models.Q(withholding_tax_percent__lte=100)
                ),
                name="purchases_vpay_wht_percent_in_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(withholding_tax_amount__gte=0),
                name="purchases_vpay_wht_amount_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(withholding_tax_amount__lte=models.F("amount")),
                name="purchases_vpay_wht_amount_not_exceeds_payment",
            ),
        ),
        # (withholding_tax_amount > 0) ⇒ withholding_tax_account IS NOT NULL
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(withholding_tax_amount=0)
                    | models.Q(withholding_tax_account__isnull=False)
                ),
                name="purchases_vpay_wht_account_required_when_wht_nonzero",
            ),
        ),
        # ------------------------------------------------------------------ #
        # PurchaseInvoiceLine                                                 #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="purchases_pinv_line_tax_amount_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="purchases_pinv_line_discount_non_negative",
            ),
        ),
    ]
