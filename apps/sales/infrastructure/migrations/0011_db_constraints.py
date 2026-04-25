"""
Phase-2 DB constraint hardening.

New constraints:
  SalesInvoice      — allocated_amount ≤ grand_total
  CustomerReceipt   — allocated_amount ≤ amount
  SalesInvoiceLine  — tax_amount ≥ 0, line_subtotal ≥ 0, line_total ≥ 0
  CreditNote        — grand_total ≥ 0 already exists; add allocated_amount ≥ 0
  DebitNote         — allocated_amount ≤ grand_total
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0010_customerreceipt_treasury_bank_account"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # SalesInvoice                                                        #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__lte=models.F("grand_total")),
                name="sales_invoice_allocated_not_exceeds_total",
            ),
        ),
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="sales_invoice_exchange_rate_positive",
            ),
        ),
        # ------------------------------------------------------------------ #
        # CustomerReceipt                                                     #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="customerreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__lte=models.F("amount")),
                name="sales_receipt_allocated_not_exceeds_amount",
            ),
        ),
        # ------------------------------------------------------------------ #
        # SalesInvoiceLine                                                    #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="sales_invoice_line_tax_amount_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(line_subtotal__gte=0),
                name="sales_invoice_line_subtotal_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="sales_invoice_line_total_non_negative",
            ),
        ),
        # ------------------------------------------------------------------ #
        # DebitNote: allocated_amount ≤ grand_total                          #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="debitnote",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__lte=models.F("grand_total")),
                name="sales_debit_note_allocated_not_exceeds_total",
            ),
        ),
    ]
