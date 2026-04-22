"""
Treasury REST API serializers — Phase 4.
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Cashbox
# ---------------------------------------------------------------------------
class CashboxReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    currency_code = serializers.CharField()
    gl_account_id = serializers.IntegerField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    current_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_active = serializers.BooleanField()
    notes = serializers.CharField()


class CashboxWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    currency_code = serializers.CharField(max_length=3, default="SAR")
    gl_account_id = serializers.IntegerField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    notes = serializers.CharField(default="", allow_blank=True)


# ---------------------------------------------------------------------------
# BankAccount
# ---------------------------------------------------------------------------
class BankAccountReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    bank_name = serializers.CharField()
    account_name = serializers.CharField()
    account_number = serializers.CharField()
    iban = serializers.CharField()
    swift_code = serializers.CharField()
    currency_code = serializers.CharField()
    gl_account_id = serializers.IntegerField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    current_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    is_active = serializers.BooleanField()
    notes = serializers.CharField()


class BankAccountWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    bank_name = serializers.CharField(max_length=128)
    account_name = serializers.CharField(max_length=128)
    account_number = serializers.CharField(max_length=64, default="", allow_blank=True)
    iban = serializers.CharField(max_length=34, default="", allow_blank=True)
    swift_code = serializers.CharField(max_length=11, default="", allow_blank=True)
    currency_code = serializers.CharField(max_length=3, default="SAR")
    gl_account_id = serializers.IntegerField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    notes = serializers.CharField(default="", allow_blank=True)


# ---------------------------------------------------------------------------
# PaymentMethod
# ---------------------------------------------------------------------------
class PaymentMethodReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    method_type = serializers.CharField()
    is_active = serializers.BooleanField()
    requires_reference = serializers.BooleanField()


class PaymentMethodWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    method_type = serializers.CharField(max_length=32)
    requires_reference = serializers.BooleanField(default=False)


# ---------------------------------------------------------------------------
# TreasuryTransaction
# ---------------------------------------------------------------------------
class TreasuryTransactionReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    transaction_number = serializers.CharField()
    transaction_date = serializers.DateField()
    transaction_type = serializers.CharField()
    cashbox_id = serializers.IntegerField(allow_null=True)
    bank_account_id = serializers.IntegerField(allow_null=True)
    contra_account_id = serializers.IntegerField()
    payment_method_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency_code = serializers.CharField()
    reference = serializers.CharField()
    notes = serializers.CharField()
    status = serializers.CharField()


class TreasuryTransactionWriteSerializer(serializers.Serializer):
    transaction_date = serializers.DateField()
    transaction_type = serializers.ChoiceField(choices=["inflow", "outflow", "adjustment"])
    cashbox_id = serializers.IntegerField(required=False, allow_null=True)
    bank_account_id = serializers.IntegerField(required=False, allow_null=True)
    contra_account_id = serializers.IntegerField()
    payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency_code = serializers.CharField(max_length=3)
    reference = serializers.CharField(max_length=64, default="", allow_blank=True)
    notes = serializers.CharField(default="", allow_blank=True)

    def validate(self, data):
        cashbox_id = data.get("cashbox_id")
        bank_account_id = data.get("bank_account_id")
        if not cashbox_id and not bank_account_id:
            raise serializers.ValidationError("Either cashbox_id or bank_account_id is required.")
        if cashbox_id and bank_account_id:
            raise serializers.ValidationError("Only one of cashbox_id or bank_account_id is allowed.")
        return data


# ---------------------------------------------------------------------------
# TreasuryTransfer
# ---------------------------------------------------------------------------
class TreasuryTransferReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    transfer_number = serializers.CharField()
    transfer_date = serializers.DateField()
    from_cashbox_id = serializers.IntegerField(allow_null=True)
    from_bank_account_id = serializers.IntegerField(allow_null=True)
    to_cashbox_id = serializers.IntegerField(allow_null=True)
    to_bank_account_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency_code = serializers.CharField()
    reference = serializers.CharField()
    notes = serializers.CharField()
    status = serializers.CharField()


class TreasuryTransferWriteSerializer(serializers.Serializer):
    transfer_date = serializers.DateField()
    from_cashbox_id = serializers.IntegerField(required=False, allow_null=True)
    from_bank_account_id = serializers.IntegerField(required=False, allow_null=True)
    to_cashbox_id = serializers.IntegerField(required=False, allow_null=True)
    to_bank_account_id = serializers.IntegerField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency_code = serializers.CharField(max_length=3)
    reference = serializers.CharField(max_length=64, default="", allow_blank=True)
    notes = serializers.CharField(default="", allow_blank=True)

    def validate(self, data):
        from_cashbox_id = data.get("from_cashbox_id")
        from_bank_account_id = data.get("from_bank_account_id")
        to_cashbox_id = data.get("to_cashbox_id")
        to_bank_account_id = data.get("to_bank_account_id")

        if not from_cashbox_id and not from_bank_account_id:
            raise serializers.ValidationError("Either from_cashbox_id or from_bank_account_id is required.")
        if from_cashbox_id and from_bank_account_id:
            raise serializers.ValidationError("Only one source (from_cashbox_id or from_bank_account_id) is allowed.")

        if not to_cashbox_id and not to_bank_account_id:
            raise serializers.ValidationError("Either to_cashbox_id or to_bank_account_id is required.")
        if to_cashbox_id and to_bank_account_id:
            raise serializers.ValidationError("Only one destination (to_cashbox_id or to_bank_account_id) is allowed.")

        return data


# ---------------------------------------------------------------------------
# BankStatement + BankStatementLine
# ---------------------------------------------------------------------------
class BankStatementLineWriteSerializer(serializers.Serializer):
    txn_date = serializers.DateField()
    description = serializers.CharField(max_length=256, default="", allow_blank=True)
    reference = serializers.CharField(max_length=64, default="", allow_blank=True)
    debit_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    credit_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    balance = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))


class BankStatementLineReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sequence = serializers.IntegerField()
    txn_date = serializers.DateField()
    description = serializers.CharField()
    reference = serializers.CharField()
    debit_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    credit_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    match_status = serializers.CharField()
    matched_transaction_id = serializers.IntegerField(allow_null=True)
    matched_at = serializers.DateTimeField(allow_null=True)


class BankStatementReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    bank_account_id = serializers.IntegerField()
    statement_date = serializers.DateField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    status = serializers.CharField()
    notes = serializers.CharField()
    imported_at = serializers.DateTimeField(allow_null=True)


class BankStatementWriteSerializer(serializers.Serializer):
    bank_account_id = serializers.IntegerField()
    statement_date = serializers.DateField()
    opening_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = serializers.DecimalField(max_digits=18, decimal_places=4)
    notes = serializers.CharField(default="", allow_blank=True)
    lines = BankStatementLineWriteSerializer(many=True, default=list)


class MatchStatementLineSerializer(serializers.Serializer):
    transaction_id = serializers.IntegerField()


# ---------------------------------------------------------------------------
# BankReconciliation
# ---------------------------------------------------------------------------
class BankReconciliationReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    bank_account_id = serializers.IntegerField()
    statement_id = serializers.IntegerField()
    difference_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    status = serializers.CharField()
    reconciled_by_id = serializers.IntegerField(allow_null=True)
    reconciled_at = serializers.DateTimeField(allow_null=True)
    notes = serializers.CharField()


class BankReconciliationWriteSerializer(serializers.Serializer):
    statement_id = serializers.IntegerField()
    notes = serializers.CharField(default="", allow_blank=True)
