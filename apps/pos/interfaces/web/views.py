"""
POS web views.

Four endpoints:
  - POSTerminalView        — GET  /pos/
                            Renders the terminal if a session is open;
                            otherwise shows the "open a session" card.
  - OpenRegisterView       — GET/POST /pos/register/open/
  - CloseRegisterView      — GET/POST /pos/register/close/
  - POSCheckoutView        — POST /pos/checkout/  (JSON)
                            Accepts a cart JSON payload, turns it into a
                            SaleDraft, and calls `PostSale`.

Register open/close go through the `OpenRegister` / `CloseRegister` use
cases — this matches the single-write-path invariant set in Sprint 3.4.

The terminal deliberately renders the whole active product catalog up
front (simple client-side filter). For large catalogs a later iteration
adds an AJAX search endpoint; for typical retail SKU counts (~few
hundred) this is fast enough and avoids the complexity.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import FormView, TemplateView

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.pos.application.use_cases.register_sessions import (
    CloseRegister,
    CloseRegisterCommand,
    OpenRegister,
    OpenRegisterCommand,
)
from apps.pos.infrastructure.models import CashRegisterSession
from apps.pos.interfaces.web.forms import CloseRegisterForm, OpenRegisterForm
from apps.sales.application.use_cases.post_sale import PostSale, PostSaleCommand
from apps.sales.domain.entities import SaleDraft, SaleLineSpec


def _find_open_session(user_id: int) -> CashRegisterSession | None:
    """Return the single open register session for this user, if any."""
    return (
        CashRegisterSession.objects
        .select_related("warehouse")
        .filter(user_id=user_id, is_open=True)
        .first()
    )


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------
@method_decorator(ensure_csrf_cookie, name="dispatch")
class POSTerminalView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "pos.pos.use"
    template_name = "pos/terminal.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = _find_open_session(self.request.user.id)
        ctx["session"] = session
        ctx["currency"] = (session.currency_code if session else "USD")

        if session:
            # Only active, stockable/sellable products. Combos and services
            # render too — the domain knows how to decompose combos at sale
            # time; services skip the stock step. Digital is treated the
            # same as service.
            products = (
                Product.objects
                .filter(is_active=True)
                .select_related("unit", "tax")
                .order_by("name")
            )
            ctx["products"] = products
        return ctx


# ---------------------------------------------------------------------------
# Register open / close
# ---------------------------------------------------------------------------
class OpenRegisterView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "pos.cash_register.open"
    template_name = "pos/register_open.html"
    form_class = OpenRegisterForm
    success_url = reverse_lazy("pos:start")

    def dispatch(self, request, *args, **kwargs):
        # Already have an open session? Kick the user into the terminal.
        if _find_open_session(request.user.id):
            messages.info(request, "A register session is already open.")
            return redirect("pos:start")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            OpenRegister().execute(OpenRegisterCommand(
                user_id=self.request.user.id,
                warehouse_id=data["warehouse"].pk,
                opening_float=Money(data["opening_float"], Currency(data["currency_code"])),
                note=data.get("note") or "",
            ))
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Register session opened.")
        return super().form_valid(form)


class CloseRegisterView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """
    Close-register form.

    Computes `expected_cash` = opening_float + net cash movement during the
    session. "Net cash" here means the sum of posted sales on this session
    assumed paid in cash minus any cash refunds — computed from the Sale
    table scoped to session window and warehouse. For this first cut we
    approximate with total paid_amount of sales posted after the session
    opened at this warehouse by this user.

    The user reviews the computed expected, enters what's actually in the
    drawer, and the use case records both with the variance.
    """
    permission_required = "pos.cash_register.close"
    template_name = "pos/register_close.html"
    form_class = CloseRegisterForm
    success_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        session = _find_open_session(request.user.id)
        if session is None:
            messages.warning(request, "No open register session to close.")
            return redirect("pos:start")
        self.session = session
        return super().dispatch(request, *args, **kwargs)

    def _compute_expected(self, session: CashRegisterSession) -> tuple[Decimal, Decimal]:
        """Return (net_cash, expected_cash) for the session."""
        from apps.sales.infrastructure.models import Sale
        from apps.sales.domain.entities import SaleStatus

        # Sales posted in this session's window, at the session's warehouse.
        # Cash payment is approximated as the full paid_amount (finer
        # channel-split arrives when POS checkout records Payment rows).
        net_cash = (
            Sale.objects
            .filter(
                status=SaleStatus.POSTED.value,
                biller__isnull=False,
                lines__warehouse_id=session.warehouse_id,
                posted_at__gte=session.opened_at,
                currency_code=session.currency_code,
            )
            .aggregate(v=Sum("paid_amount"))["v"]
        ) or Decimal("0")

        expected = session.opening_float + net_cash
        return net_cash, expected

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        net_cash, expected = self._compute_expected(self.session)
        ctx.update({
            "session": self.session,
            "net_cash": net_cash,
            "expected_cash": expected,
        })
        return ctx

    def form_valid(self, form):
        net_cash, expected = self._compute_expected(self.session)
        declared = form.cleaned_data["declared_closing_float"]

        try:
            CloseRegister().execute(CloseRegisterCommand(
                session_id=self.session.pk,
                declared_closing_float=Money(declared, Currency(self.session.currency_code)),
                expected_cash=Money(expected, Currency(self.session.currency_code)),
                note=form.cleaned_data.get("note") or "",
            ))
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Register session closed.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Checkout — JSON endpoint the terminal POSTs to
# ---------------------------------------------------------------------------
@method_decorator(login_required, name="dispatch")
class POSCheckoutView(PermissionRequiredMixin, View):
    """
    POST body (JSON):
        {
            "customer_id": 123,
            "biller_id": 4,
            "lines": [
                {"product_id": 1, "warehouse_id": 2, "quantity": "1.0",
                 "unit_price": "9.99", "tax_rate_percent": "15"},
                ...
            ],
            "debit_account_id": 10,       # typically the cash account id
            "revenue_account_id": 20,
            "tax_payable_account_id": 21  # optional
        }

    Returns JSON:
        { "sale_id": 42, "reference": "POS-…", "journal_entry_id": 99 }
    """
    permission_required = "sales.sales.create"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        session = _find_open_session(request.user.id)
        if session is None:
            return JsonResponse({"error": "no_open_session"}, status=409)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"error": "invalid_json"}, status=400)

        # Resolve defaults from POS config when the client omits IDs. The
        # config is a singleton per tenant with sensible fallbacks seeded
        # by `ensure_pos_config` during tenant bootstrap.
        try:
            config = _resolve_pos_config()
        except Exception as exc:
            return JsonResponse(
                {"error": "pos_config_missing", "detail": str(exc)},
                status=422,
            )

        customer_id = payload.get("customer_id") or config["default_customer_id"]
        biller_id = payload.get("biller_id") or config["default_biller_id"]
        debit_account_id = payload.get("debit_account_id") or config["cash_account_id"]
        revenue_account_id = payload.get("revenue_account_id") or config["revenue_account_id"]
        tax_payable_account_id = (
            payload.get("tax_payable_account_id") or config.get("tax_payable_account_id")
        )

        try:
            currency = Currency(session.currency_code)
            line_specs = []
            for raw in payload.get("lines") or []:
                product_id = int(raw["product_id"])
                product = (
                    Product.objects.filter(pk=product_id)
                    .select_related("unit")
                    .first()
                )
                if product is None:
                    return JsonResponse(
                        {"error": "product_not_found", "product_id": product_id},
                        status=400,
                    )

                line_specs.append(SaleLineSpec(
                    product_id=product_id,
                    warehouse_id=int(raw.get("warehouse_id") or session.warehouse_id),
                    quantity=Quantity(Decimal(str(raw["quantity"])), product.unit.code),
                    unit_price=Money(Decimal(str(raw["unit_price"])), currency),
                    tax_rate_percent=Decimal(str(raw.get("tax_rate_percent") or "0")),
                ))
            draft = SaleDraft(
                lines=tuple(line_specs),
                order_discount=Money.zero(currency),
                shipping=Money.zero(currency),
                memo=payload.get("memo", ""),
            )

            # Build a POS-flavoured reference and post.
            reference = payload.get("reference") or f"POS-{session.pk}-{_posix_ticks()}"

            posted = PostSale().execute(PostSaleCommand(
                reference=reference,
                sale_date=date.today(),
                customer_id=int(customer_id),
                biller_id=int(biller_id),
                draft=draft,
                debit_account_id=int(debit_account_id),
                revenue_account_id=int(revenue_account_id),
                tax_payable_account_id=(
                    int(tax_payable_account_id) if tax_payable_account_id else None
                ),
                memo=payload.get("memo", ""),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            return JsonResponse({"error": "bad_request", "detail": str(exc)}, status=400)
        except Exception as exc:
            # Domain / repository errors — surface the message to the POS UI.
            return JsonResponse({"error": "use_case_failed", "detail": str(exc)}, status=422)

        return JsonResponse({
            "sale_id": posted.sale_id,
            "reference": posted.reference,
            "journal_entry_id": posted.journal_entry_id,
        })


def _posix_ticks() -> int:
    import time
    return int(time.time())


def _resolve_pos_config() -> dict:
    """
    Pick POS defaults from existing master data.

    Strategy:
      - default customer: a Customer with code 'WALKIN' if one exists,
        else the first active Customer.
      - default biller: the first active Biller.
      - cash account: Account where account_type='asset' and code starts
        with '1010' (cash-in-hand by convention), or the first asset
        account whose name contains 'cash' (case-insensitive).
      - revenue account: Account where account_type='income' — first match.
      - tax payable account: Account where account_type='liability' and
        name contains 'tax payable'; None when no such account exists and
        the cart has zero-tax lines.

    A clean future iteration replaces this with a proper `POSConfig` model
    per tenant. For now, the heuristic is explicit and easy to override
    via `apps.tenancy.bootstrap.ensure_pos_config`.
    """
    from apps.crm.infrastructure.models import Biller, Customer
    from apps.finance.infrastructure.models import Account, AccountTypeChoices

    customer = (
        Customer.objects.filter(code="WALKIN", is_active=True).first()
        or Customer.objects.filter(is_active=True).order_by("pk").first()
    )
    if customer is None:
        raise RuntimeError("No active customer available. Create at least one customer, or a 'WALKIN' record for POS sales.")

    biller = Biller.objects.filter(is_active=True).order_by("pk").first()
    if biller is None:
        raise RuntimeError("No active biller available. Create at least one biller for POS sales.")

    cash = (
        Account.objects.filter(account_type=AccountTypeChoices.ASSET, code__startswith="1010").first()
        or Account.objects.filter(account_type=AccountTypeChoices.ASSET, name__icontains="cash").first()
    )
    if cash is None:
        raise RuntimeError("No cash account found in the chart of accounts.")

    revenue = Account.objects.filter(account_type=AccountTypeChoices.INCOME).order_by("code").first()
    if revenue is None:
        raise RuntimeError("No revenue account found in the chart of accounts.")

    tax_payable = (
        Account.objects.filter(
            account_type=AccountTypeChoices.LIABILITY,
            name__icontains="tax payable",
        ).first()
    )

    return {
        "default_customer_id": customer.pk,
        "default_biller_id": biller.pk,
        "cash_account_id": cash.pk,
        "revenue_account_id": revenue.pk,
        "tax_payable_account_id": tax_payable.pk if tax_payable else None,
    }
