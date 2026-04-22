"""
Phase 2: Sales & Receivables cycle models.

Creates:
  - sales_invoice
  - sales_invoice_line
  - sales_customer_receipt
  - sales_customer_receipt_allocation
  - sales_credit_note
  - sales_credit_note_line
  - sales_debit_note
  - sales_debit_note_line
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_sale_returned_amount_salereturn_salereturnline_and_more"),
        ("crm", "0002_customer_phase2_fields"),
        ("finance", "0006_taxcode_taxprofile"),
        ("tenancy", "0003_organization_phase12_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ---------------------------------------------------------------
        # SalesInvoice
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="SalesInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
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
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_invoices", to="crm.customer")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_invoices", to="tenancy.branch")),
                ("fiscal_period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_invoices", to="finance.accountingperiod")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_invoice", to="finance.journalentry")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_sales_invoices", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_invoice", "ordering": ("-invoice_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.UniqueConstraint(fields=("organization", "invoice_number"), name="sales_invoice_unique_number_per_org"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="sales_invoice_grand_total_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.CheckConstraint(condition=models.Q(due_date__gte=models.F("invoice_date")), name="sales_invoice_due_after_invoice"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoice",
            constraint=models.CheckConstraint(condition=models.Q(allocated_amount__gte=0), name="sales_invoice_allocated_non_negative"),
        ),
        migrations.AddIndex(
            model_name="salesinvoice",
            index=models.Index(fields=["organization", "customer", "invoice_date"], name="sales_inv_org_cust_date_idx"),
        ),
        migrations.AddIndex(
            model_name="salesinvoice",
            index=models.Index(fields=["organization", "status", "due_date"], name="sales_inv_org_status_due_idx"),
        ),

        # ---------------------------------------------------------------
        # SalesInvoiceLine
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="SalesInvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("item_code", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("discount_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_subtotal", models.DecimalField(decimal_places=4, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="sales.salesinvoice")),
                ("tax_code", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="invoice_lines", to="finance.taxcode")),
                ("revenue_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="invoice_lines", to="finance.account")),
            ],
            options={"db_table": "sales_invoice_line", "ordering": ("invoice_id", "sequence")},
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.UniqueConstraint(fields=("invoice", "sequence"), name="sales_invoice_line_unique_seq_per_invoice"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_invoice_line_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="sales_invoice_line_unit_price_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="salesinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="sales_invoice_line_discount_non_negative"),
        ),

        # ---------------------------------------------------------------
        # CustomerReceipt
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="CustomerReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("receipt_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("receipt_date", models.DateField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency_code", models.CharField(max_length=3)),
                ("payment_method", models.CharField(blank=True, default="", max_length=32)),
                ("reference", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled"), ("reversed", "Reversed")],
                    db_index=True, default="draft", max_length=12,
                )),
                ("allocated_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="crm.customer")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customer_receipts", to="tenancy.branch")),
                ("fiscal_period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customer_receipts", to="finance.accountingperiod")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customer_receipt", to="finance.journalentry")),
                ("bank_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="receipt_bank_side", to="finance.account")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_customer_receipt", "ordering": ("-receipt_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="customerreceipt",
            constraint=models.CheckConstraint(condition=models.Q(amount__gt=0), name="sales_customer_receipt_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="customerreceipt",
            constraint=models.CheckConstraint(condition=models.Q(allocated_amount__gte=0), name="sales_customer_receipt_allocated_non_negative"),
        ),
        migrations.AddIndex(
            model_name="customerreceipt",
            index=models.Index(fields=["organization", "customer", "receipt_date"], name="sales_rcpt_org_cust_date_idx"),
        ),
        migrations.AddIndex(
            model_name="customerreceipt",
            index=models.Index(fields=["organization", "status"], name="sales_rcpt_org_status_idx"),
        ),

        # ---------------------------------------------------------------
        # CustomerReceiptAllocation
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="CustomerReceiptAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allocated_amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("receipt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="sales.customerreceipt")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="sales.salesinvoice")),
            ],
            options={"db_table": "sales_customer_receipt_allocation", "ordering": ("receipt_id", "id")},
        ),
        migrations.AddConstraint(
            model_name="customerreceiptallocation",
            constraint=models.UniqueConstraint(fields=("receipt", "invoice"), name="sales_receipt_allocation_unique_per_invoice"),
        ),
        migrations.AddConstraint(
            model_name="customerreceiptallocation",
            constraint=models.CheckConstraint(condition=models.Q(allocated_amount__gt=0), name="sales_receipt_allocation_amount_positive"),
        ),

        # ---------------------------------------------------------------
        # CreditNote
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="CreditNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("note_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("note_date", models.DateField(db_index=True)),
                ("reason", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("issued", "Issued"), ("applied", "Applied"), ("cancelled", "Cancelled")],
                    db_index=True, default="draft", max_length=12,
                )),
                ("subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("currency_code", models.CharField(blank=True, default="", max_length=3)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="credit_notes", to="crm.customer")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_notes", to="tenancy.branch")),
                ("related_invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_notes", to="sales.salesinvoice")),
                ("fiscal_period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_notes", to="finance.accountingperiod")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_note", to="finance.journalentry")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_credit_notes", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_credit_note", "ordering": ("-note_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="creditnote",
            constraint=models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="sales_credit_note_grand_total_non_negative"),
        ),
        migrations.AddIndex(
            model_name="creditnote",
            index=models.Index(fields=["organization", "customer", "note_date"], name="sales_cn_org_cust_date_idx"),
        ),
        migrations.AddIndex(
            model_name="creditnote",
            index=models.Index(fields=["organization", "status"], name="sales_cn_org_status_idx"),
        ),

        # CreditNoteLine
        migrations.CreateModel(
            name="CreditNoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("quantity", models.DecimalField(decimal_places=4, default=1, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("credit_note", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="sales.creditnote")),
                ("tax_code", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_note_lines", to="finance.taxcode")),
                ("revenue_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credit_note_lines", to="finance.account")),
            ],
            options={"db_table": "sales_credit_note_line", "ordering": ("credit_note_id", "sequence")},
        ),
        migrations.AddConstraint(
            model_name="creditnoteline",
            constraint=models.UniqueConstraint(fields=("credit_note", "sequence"), name="sales_credit_note_line_unique_seq"),
        ),
        migrations.AddConstraint(
            model_name="creditnoteline",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_credit_note_line_qty_positive"),
        ),

        # ---------------------------------------------------------------
        # DebitNote
        # ---------------------------------------------------------------
        migrations.CreateModel(
            name="DebitNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("note_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("note_date", models.DateField(db_index=True)),
                ("reason", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("issued", "Issued"), ("applied", "Applied"), ("cancelled", "Cancelled")],
                    db_index=True, default="draft", max_length=12,
                )),
                ("subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("currency_code", models.CharField(blank=True, default="", max_length=3)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="debit_notes", to="crm.customer")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_notes", to="tenancy.branch")),
                ("related_invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_notes", to="sales.salesinvoice")),
                ("fiscal_period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_notes", to="finance.accountingperiod")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_note", to="finance.journalentry")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_debit_notes", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_debit_note", "ordering": ("-note_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="debitnote",
            constraint=models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="sales_debit_note_grand_total_non_negative"),
        ),
        migrations.AddIndex(
            model_name="debitnote",
            index=models.Index(fields=["organization", "customer", "note_date"], name="sales_dn_org_cust_date_idx"),
        ),
        migrations.AddIndex(
            model_name="debitnote",
            index=models.Index(fields=["organization", "status"], name="sales_dn_org_status_idx"),
        ),

        # DebitNoteLine
        migrations.CreateModel(
            name="DebitNoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("quantity", models.DecimalField(decimal_places=4, default=1, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("debit_note", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="sales.debitnote")),
                ("tax_code", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_note_lines", to="finance.taxcode")),
                ("revenue_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="debit_note_lines", to="finance.account")),
            ],
            options={"db_table": "sales_debit_note_line", "ordering": ("debit_note_id", "sequence")},
        ),
        migrations.AddConstraint(
            model_name="debitnoteline",
            constraint=models.UniqueConstraint(fields=("debit_note", "sequence"), name="sales_debit_note_line_unique_seq"),
        ),
        migrations.AddConstraint(
            model_name="debitnoteline",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_debit_note_line_qty_positive"),
        ),
    ]
