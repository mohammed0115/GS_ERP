# Generated migration for DeliveryNote aggregate (Gap 4).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0004_salequotation"),
        ("catalog", "0001_initial"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliveryNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reference", models.CharField(db_index=True, max_length=64)),
                ("delivery_date", models.DateField(db_index=True)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("dispatched", "Dispatched"), ("delivered", "Delivered"), ("cancelled", "Cancelled")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("carrier", models.CharField(blank=True, default="", max_length=128)),
                ("tracking_number", models.CharField(blank=True, default="", max_length=128)),
                ("notes", models.TextField(blank=True, default="")),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="sales.sale")),
                ("created_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "sales_delivery_note", "ordering": ("-delivery_date", "-id")},
        ),
        migrations.AddConstraint(
            model_name="deliverynote",
            constraint=models.UniqueConstraint(fields=("organization", "reference"), name="sales_delivery_note_unique_reference_per_org"),
        ),
        migrations.AddIndex(
            model_name="deliverynote",
            index=models.Index(fields=["organization", "sale", "status"], name="sales_delivnote_org_sale_idx"),
        ),
        migrations.CreateModel(
            name="DeliveryNoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("line_number", models.PositiveSmallIntegerField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("uom_code", models.CharField(max_length=16)),
                ("note", models.TextField(blank=True, default="")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("delivery_note", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="sales.deliverynote")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_lines", to="catalog.product")),
            ],
            options={"db_table": "sales_delivery_note_line", "ordering": ("delivery_note_id", "line_number")},
        ),
        migrations.AddConstraint(
            model_name="deliverynoteline",
            constraint=models.UniqueConstraint(fields=("delivery_note", "line_number"), name="sales_delivery_line_unique_line_number"),
        ),
        migrations.AddConstraint(
            model_name="deliverynoteline",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_delivery_line_quantity_positive"),
        ),
    ]
