"""Dashboard HTML view — renders KPIs from the reports selectors."""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.sales.infrastructure.models import Sale
from apps.sales.domain.entities import SaleStatus
from apps.reports.application import selectors


@login_required
def home(request):

    today = date.today()
    first_of_month = today.replace(day=1)
    thirty_days_ago = today - timedelta(days=30)

    today_sales = (
        Sale.objects.filter(status=SaleStatus.POSTED.value, sale_date=today)
        .aggregate(t=Sum("grand_total"))["t"]
    ) or Decimal("0")

    # This month
    month_sales = (
        Sale.objects.filter(
            status=SaleStatus.POSTED.value,
            sale_date__gte=first_of_month,
            sale_date__lte=today,
        )
        .aggregate(t=Sum("grand_total"))["t"]
    ) or Decimal("0")

    # Outstanding receivables
    due_rows = selectors.due_receivables(as_of=today)
    outstanding = sum((r.total_due for r in due_rows), start=Decimal("0"))

    # Liquidity summary
    try:
        liquidity = selectors.liquidity_summary()
    except Exception:
        liquidity = []

    # Low stock
    low_stock = selectors.low_stock_alert()

    # Best sellers
    best_sellers = selectors.best_sellers(
        date_from=thirty_days_ago, date_to=today, limit=10,
    )

    org = getattr(request, "organization", None)
    currency = (org.default_currency_code if org else None) or "SAR"

    context = {
        "site_title": "GS ERP",
        "currency": currency,
        "kpis": {
            "today_sales": today_sales,
            "month_sales": month_sales,
            "outstanding": outstanding,
            "low_stock_count": len(low_stock),
        },
        "liquidity": liquidity,
        "low_stock": low_stock,
        "best_sellers": best_sellers,
        "best_sellers_labels": json.dumps([r.product_code for r in best_sellers]),
        "best_sellers_values": json.dumps([str(r.quantity_sold) for r in best_sellers]),
    }
    return render(request, "dashboard/home.html", context)
