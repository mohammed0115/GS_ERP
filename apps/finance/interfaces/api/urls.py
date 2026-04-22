"""Finance REST API URL configuration (Phase 6)."""
from django.urls import path

from apps.finance.interfaces.api.views import (
    AdjustmentEntryDetailView,
    AdjustmentEntryListView,
    ClosePeriodView,
    ClosingChecklistDetailView,
    ClosingChecklistGenerateView,
    ClosingChecklistItemMarkView,
    ClosingRunDetailView,
    PeriodSignOffView,
    ReopenPeriodView,
    ReportLineDetailView,
    ReportLineListView,
    TaxCodeDetailView,
    TaxCodeListView,
    TaxProfileDetailView,
    TaxProfileListView,
    TaxTransactionListView,
)

app_name = "finance_api"

urlpatterns = [
    # Tax codes
    path("tax-codes/", TaxCodeListView.as_view(), name="taxcode-list"),
    path("tax-codes/<int:pk>/", TaxCodeDetailView.as_view(), name="taxcode-detail"),

    # Tax profiles
    path("tax-profiles/", TaxProfileListView.as_view(), name="taxprofile-list"),
    path("tax-profiles/<int:pk>/", TaxProfileDetailView.as_view(), name="taxprofile-detail"),

    # Tax transactions (audit trail — read-only)
    path("tax-transactions/", TaxTransactionListView.as_view(), name="taxtxn-list"),

    # Adjustment entries
    path("adjustment-entries/", AdjustmentEntryListView.as_view(), name="adjustment-list"),
    path("adjustment-entries/<int:pk>/", AdjustmentEntryDetailView.as_view(), name="adjustment-detail"),

    # Period close workflow
    path("close-period/", ClosePeriodView.as_view(), name="close-period"),
    path("periods/<int:period_pk>/reopen/", ReopenPeriodView.as_view(), name="reopen-period"),

    # Closing checklist
    path("periods/<int:period_pk>/checklist/", ClosingChecklistDetailView.as_view(), name="checklist-detail"),
    path("periods/<int:period_pk>/checklist/generate/", ClosingChecklistGenerateView.as_view(), name="checklist-generate"),
    path("periods/<int:period_pk>/checklist/items/<int:item_pk>/mark/", ClosingChecklistItemMarkView.as_view(), name="checklist-item-mark"),

    # Closing run (read-only)
    path("periods/<int:period_pk>/closing-run/", ClosingRunDetailView.as_view(), name="closing-run"),

    # Period sign-off
    path("periods/<int:period_pk>/sign-off/", PeriodSignOffView.as_view(), name="sign-off"),

    # Report lines
    path("report-lines/", ReportLineListView.as_view(), name="reportline-list"),
    path("report-lines/<int:pk>/", ReportLineDetailView.as_view(), name="reportline-detail"),
]
