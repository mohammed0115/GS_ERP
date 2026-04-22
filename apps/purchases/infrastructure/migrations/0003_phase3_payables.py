"""Phase 3 — PurchaseInvoice, VendorPayment, VendorCreditNote, VendorDebitNote."""
from __future__ import annotations

import django.db.models.deletion
import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0002_purchase_returned_amount_purchasereturn_and_more"),
        ("crm", "0003_supplier_phase3_fields"),
        ("finance", "0006_taxcode_taxprofile"),
        ("tenancy", "0003_organization_phase12_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---------------------------------------------------------------
        # PurchaseInvoice
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="PurchaseInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("vendor_invoice_number", models.CharField(blank=True, default="", max_length=64)),
                ("invoice_date", models.DateField(db_index=True)),
                ("due_date", models.DateField()),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"), ("issued", "Issued"),
                        ("partially_paid", "Partially Paid"), ("paid", "Paid"),
                        ("cancelled", "Cancelled"), ("credited", "Credited"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("currency_code", models.CharField(max_length=3)),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=1, max_digits=18)),
                ("subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("discount_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("allocated_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("notes", models.TextField(blank=True, default="")),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("vendor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoices",
                    to="crm.supplier",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoices",
                    to="tenancy.branch",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoices",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoice",
                    to="finance.journalentry",
                )),
                ("issued_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="issued_purchase_invoices",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "purchases_purchase_invoice", "ordering": ["-invoice_date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(due_date__gte=django.db.models.expressions.F("invoice_date")),
                name="purchases_pinv_due_date_after_invoice_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="purchases_pinv_grand_total_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="purchases_pinv_allocated_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(fields=["organization", "vendor", "invoice_date"], name="purchases_pinv_org_vendor_date"),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(fields=["organization", "status", "due_date"], name="purchases_pinv_org_status_due"),
        ),

        # ---------------------------------------------------------------
        # PurchaseInvoiceLine
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="PurchaseInvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("item_code", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.CharField(max_length=256)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("discount_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_subtotal", models.DecimalField(decimal_places=4, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("invoice", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lines",
                    to="purchases.purchaseinvoice",
                )),
                ("tax_code", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoice_lines",
                    to="finance.taxcode",
                )),
                ("expense_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_invoice_lines",
                    to="finance.account",
                )),
            ],
            options={"db_table": "purchases_purchase_invoice_line", "ordering": ["invoice_id", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.UniqueConstraint(
                fields=["invoice", "sequence"], name="purchases_pinv_line_unique_sequence"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="purchases_pinv_line_quantity_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="purchases_pinv_line_unit_price_non_negative"
            ),
        ),

        # ---------------------------------------------------------------
        # VendorPayment
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="VendorPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("payment_date", models.DateField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency_code", models.CharField(max_length=3)),
                ("payment_method", models.CharField(
                    choices=[
                        ("cash", "Cash"), ("bank_transfer", "Bank Transfer"),
                        ("cheque", "Cheque"), ("card", "Card"), ("other", "Other"),
                    ],
                    default="bank_transfer", max_length=32,
                )),
                ("reference", models.CharField(blank=True, default="", max_length=64)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"), ("posted", "Posted"),
                        ("cancelled", "Cancelled"), ("reversed", "Reversed"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("allocated_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("vendor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_payments",
                    to="crm.supplier",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_payments",
                    to="tenancy.branch",
                )),
                ("bank_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_payments",
                    to="finance.account",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_payments",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_payment",
                    to="finance.journalentry",
                )),
            ],
            options={"db_table": "purchases_vendor_payment", "ordering": ["-payment_date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="purchases_vpay_amount_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="purchases_vpay_allocated_non_negative",
            ),
        ),

        # ---------------------------------------------------------------
        # VendorPaymentAllocation
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="VendorPaymentAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allocated_amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("payment", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="allocations",
                    to="purchases.vendorpayment",
                )),
                ("invoice", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payment_allocations",
                    to="purchases.purchaseinvoice",
                )),
            ],
            options={"db_table": "purchases_vendor_payment_allocation"},
        ),
        migrations.AddConstraint(
            model_name="vendorpaymentallocation",
            constraint=models.UniqueConstraint(
                fields=["payment", "invoice"],
                name="purchases_vpay_alloc_unique_payment_invoice",
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorpaymentallocation",
            constraint=models.CheckConstraint(
                condition=models.Q(allocated_amount__gt=0),
                name="purchases_vpay_alloc_amount_positive",
            ),
        ),

        # ---------------------------------------------------------------
        # VendorCreditNote + Lines
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="VendorCreditNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("note_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("note_date", models.DateField(db_index=True)),
                ("reason", models.CharField(blank=True, default="", max_length=256)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"), ("issued", "Issued"),
                        ("applied", "Applied"), ("cancelled", "Cancelled"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("currency_code", models.CharField(max_length=3)),
                ("subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("vendor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_credit_notes",
                    to="crm.supplier",
                )),
                ("related_invoice", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="credit_notes",
                    to="purchases.purchaseinvoice",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_credit_notes",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_credit_note",
                    to="finance.journalentry",
                )),
                ("issued_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="issued_vendor_credit_notes",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "purchases_vendor_credit_note", "ordering": ["-note_date", "-id"]},
        ),
        migrations.CreateModel(
            name="VendorCreditNoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("description", models.CharField(max_length=256)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("credit_note", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lines",
                    to="purchases.vendorcreditnote",
                )),
                ("tax_code", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_credit_note_lines",
                    to="finance.taxcode",
                )),
                ("expense_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_credit_note_lines",
                    to="finance.account",
                )),
            ],
            options={"db_table": "purchases_vendor_credit_note_line", "ordering": ["credit_note_id", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="vendorcreditnoteline",
            constraint=models.UniqueConstraint(
                fields=["credit_note", "sequence"], name="purchases_vcn_line_unique_sequence"
            ),
        ),

        # ---------------------------------------------------------------
        # VendorDebitNote + Lines
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="VendorDebitNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("note_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("note_date", models.DateField(db_index=True)),
                ("reason", models.CharField(blank=True, default="", max_length=256)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"), ("issued", "Issued"),
                        ("applied", "Applied"), ("cancelled", "Cancelled"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("currency_code", models.CharField(max_length=3)),
                ("subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("vendor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_debit_notes",
                    to="crm.supplier",
                )),
                ("related_invoice", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="debit_notes",
                    to="purchases.purchaseinvoice",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_debit_notes",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_debit_note",
                    to="finance.journalentry",
                )),
                ("issued_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="issued_vendor_debit_notes",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "purchases_vendor_debit_note", "ordering": ["-note_date", "-id"]},
        ),
        migrations.CreateModel(
            name="VendorDebitNoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("description", models.CharField(max_length=256)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="tenancy.organization",
                )),
                ("debit_note", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lines",
                    to="purchases.vendordebitnote",
                )),
                ("tax_code", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_debit_note_lines",
                    to="finance.taxcode",
                )),
                ("expense_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="vendor_debit_note_lines",
                    to="finance.account",
                )),
            ],
            options={"db_table": "purchases_vendor_debit_note_line", "ordering": ["debit_note_id", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="vendordebitnoteline",
            constraint=models.UniqueConstraint(
                fields=["debit_note", "sequence"], name="purchases_vdn_line_unique_sequence"
            ),
        ),
    ]
