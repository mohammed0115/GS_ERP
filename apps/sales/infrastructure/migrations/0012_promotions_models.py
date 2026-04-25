"""Add legacy-style promotions models: coupons + gift cards."""

from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0011_db_constraints"),
        ("crm", "0001_initial"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # Coupon                                                             #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="Coupon",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=64)),
                ("type", models.CharField(choices=[("percentage", "Percentage"), ("fixed", "Fixed Amount")], max_length=16)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("minimum_amount", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("used", models.PositiveIntegerField(default=0)),
                ("expired_date", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={
                "db_table": "sales_coupon",
                "ordering": ("-id",),
            },
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["organization", "is_active", "expired_date"], name="sales_coupon_organiz_2b6b4c_idx"),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.UniqueConstraint(fields=("organization", "code"), name="sales_coupon_unique_code_per_org"),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="sales_coupon_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="sales_coupon_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(condition=models.Q(("used__gte", 0)), name="sales_coupon_used_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(condition=models.Q(("used__lte", models.F("quantity"))), name="sales_coupon_used_not_exceeds_quantity"),
        ),

        # ------------------------------------------------------------------ #
        # GiftCard                                                           #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="GiftCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("card_no", models.CharField(db_index=True, max_length=64)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("expense", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("expired_date", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_by", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="gift_cards", to="crm.customer")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="gift_cards", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "sales_gift_card",
                "ordering": ("-id",),
            },
        ),
        migrations.AddIndex(
            model_name="giftcard",
            index=models.Index(fields=["organization", "is_active", "expired_date"], name="sales_gift_c_organiz_02d4b8_idx"),
        ),
        migrations.AddConstraint(
            model_name="giftcard",
            constraint=models.UniqueConstraint(fields=("organization", "card_no"), name="sales_gift_card_unique_card_no_per_org"),
        ),
        migrations.AddConstraint(
            model_name="giftcard",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="sales_gift_card_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="giftcard",
            constraint=models.CheckConstraint(condition=models.Q(("expense__gte", 0)), name="sales_gift_card_expense_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="giftcard",
            constraint=models.CheckConstraint(condition=models.Q(("expense__lte", models.F("amount"))), name="sales_gift_card_expense_not_exceeds_amount"),
        ),

        # ------------------------------------------------------------------ #
        # GiftCardRecharge                                                    #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="GiftCardRecharge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("gift_card", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recharges", to="sales.giftcard")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("user", models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "sales_gift_card_recharge",
                "ordering": ("-id",),
            },
        ),
        migrations.AddConstraint(
            model_name="giftcardrecharge",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="sales_gift_card_recharge_amount_positive"),
        ),
    ]

