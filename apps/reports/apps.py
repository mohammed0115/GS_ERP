from __future__ import annotations
from django.apps import AppConfig

class ReportsConfig(AppConfig):
    name = "apps.reports"
    label = "reports"
    verbose_name = "Reports"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("reports", (
            "low_stock", "warehouse_stock", "daily_sales", "monthly_sales",
            "daily_purchases", "monthly_purchases", "best_sellers",
            "profit_loss", "product_sales", "sales_report", "purchase_report",
            "payment_report", "customer_report", "supplier_report",
            "user_report", "due_report",
            "income_statement", "general_ledger", "trial_balance",
            "balance_sheet", "ar_aging", "ap_aging",
            "customer_statement", "vendor_statement",
        ))
