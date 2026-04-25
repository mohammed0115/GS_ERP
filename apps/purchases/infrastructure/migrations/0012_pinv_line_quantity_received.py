"""
Add quantity_received to PurchaseInvoiceLine.

Tracks how much of each invoiced line has been physically received into stock.
Incremented atomically by IssuePurchaseInvoice; used by the over-receipt guard
to prevent receiving more than was invoiced.

Two DB constraints enforce the invariant at the PostgreSQL level:
  - quantity_received ≥ 0
  - quantity_received ≤ quantity  (cannot receive more than invoiced)
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0011_db_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="quantity_received",
            field=models.DecimalField(
                max_digits=18,
                decimal_places=4,
                default=0,
                help_text="Cumulative quantity physically received into stock.",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0),
                name="purchases_pinv_line_quantity_received_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_received__lte=models.F("quantity")),
                name="purchases_pinv_line_quantity_received_not_exceeds_invoiced",
            ),
        ),
    ]
