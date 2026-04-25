"""
Phase-4 DB constraint hardening.

New constraints:
  BankStatementLine  — at most ONE match target set at a time
                       (matched_transaction XOR matched_receipt XOR matched_vendor_payment)
  TreasuryTransaction — status enum {draft, posted, reversed}
  TreasuryTransfer    — status enum {draft, posted, reversed}
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("treasury", "0004_bankstatementline_match_fields"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # BankStatementLine: only one of the three match FKs may be set      #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="bankstatementline",
            constraint=models.CheckConstraint(
                condition=(
                    # all null (unmatched)
                    models.Q(
                        matched_transaction_id__isnull=True,
                        matched_receipt_id__isnull=True,
                        matched_vendor_payment_id__isnull=True,
                    )
                    # only matched_transaction set
                    | models.Q(
                        matched_transaction_id__isnull=False,
                        matched_receipt_id__isnull=True,
                        matched_vendor_payment_id__isnull=True,
                    )
                    # only matched_receipt set
                    | models.Q(
                        matched_transaction_id__isnull=True,
                        matched_receipt_id__isnull=False,
                        matched_vendor_payment_id__isnull=True,
                    )
                    # only matched_vendor_payment set
                    | models.Q(
                        matched_transaction_id__isnull=True,
                        matched_receipt_id__isnull=True,
                        matched_vendor_payment_id__isnull=False,
                    )
                ),
                name="treasury_stmt_line_single_match_target",
            ),
        ),
        # ------------------------------------------------------------------ #
        # TreasuryTransaction: status enum                                   #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="treasurytransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["draft", "posted", "reversed"]),
                name="treasury_txn_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="treasurytransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(transaction_type__in=["inflow", "outflow", "adjustment"]),
                name="treasury_txn_type_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # TreasuryTransfer: status enum                                      #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["draft", "posted", "reversed"]),
                name="treasury_transfer_status_valid",
            ),
        ),
    ]
