# Generated migration for SaleQuotation aggregate (Gap 3 — ADR-020).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_phase2_sales_cycle"),
        ("crm", "0001_initial"),
        ("catalog", "0001_initial"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SaleQuotation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reference", models.CharField(db_index=True, max_length=64)),
                ("quotation_date", models.DateField(db_index=True)),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("sent", "Sent"), ("accepted", "Accepted"),
                             ("converted", "Converted"), ("expired", "Expired"), ("declined", "Declined")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("currency_code", models.CharField(max_length=3)),
                ("total_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("lines_subtotal", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("lines_discount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("lines_tax", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("notes", models.TextField(blank=True, default="")),
                ("converted_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quotations", to="crm.customer")),
                ("converted_sale", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="quotation", to="sales.sale",
                )),
                ("created_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_sale_quotation", "ordering": ("-quotation_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="salequotation",
            constraint=models.UniqueConstraint(fields=("organization", "reference"), name="sales_quotation_unique_reference_per_org"),
        ),
        migrations.AddIndex(
            model_name="salequotation",
            index=models.Index(fields=["organization", "customer", "status"], name="sales_quot_org_cust_status_idx"),
        ),
        migrations.AddIndex(
            model_name="salequotation",
            index=models.Index(fields=["organization", "status", "valid_until"], name="sales_quot_org_status_expiry_idx"),
        ),
        migrations.CreateModel(
            name="SaleQuotationLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("line_number", models.PositiveSmallIntegerField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("uom_code", models.CharField(max_length=16)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("discount_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("tax_rate_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("line_subtotal", models.DecimalField(decimal_places=4, max_digits=18)),
                ("line_discount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("line_tax", models.DecimalField(decimal_places=4, max_digits=18)),
                ("line_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("quotation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="sales.salequotation")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quotation_lines", to="catalog.product")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quotation_lines", to="catalog.productvariant")),
            ],
            options={"db_table": "sales_sale_quotation_line", "ordering": ("quotation_id", "line_number")},
        ),
        migrations.AddConstraint(
            model_name="salequotationline",
            constraint=models.UniqueConstraint(fields=("quotation", "line_number"), name="sales_quotation_line_unique_line_number"),
        ),
    ]
