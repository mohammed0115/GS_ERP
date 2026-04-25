"""
System settings web views.

Currently limited to Currency CRUD. Future scope: tenant preferences,
POS config, ledger account conventions, email settings, etc.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.infrastructure.models import Currency
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Organization
from common.forms import BootstrapFormMixin


class StaffRequiredMixin(UserPassesTestMixin):
    """Gate settings pages to staff users and org admins."""

    def test_func(self) -> bool:
        u = self.request.user  # type: ignore[attr-defined]
        if not u.is_authenticated:
            return False
        if u.is_staff or u.is_superuser:
            return True
        return u.memberships.filter(role="admin", is_active=True).exists()


# ---------------------------------------------------------------------------
# Currency CRUD
# ---------------------------------------------------------------------------
class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "minor_units", "is_active"]

    def clean_code(self):
        value = (self.cleaned_data.get("code") or "").upper()
        # Match the DB-level check constraint: three uppercase letters.
        if not (len(value) == 3 and value.isalpha() and value.isupper()):
            raise forms.ValidationError("Must be a 3-letter ISO-4217 code (e.g. USD, EUR, SAR).")
        return value


class CurrencyListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = Currency
    template_name = "catalog/currency/list.html"
    context_object_name = "object_list"
    paginate_by = 50
    ordering = "code"


class CurrencyCreateView(LoginRequiredMixin, StaffRequiredMixin,
                         SuccessMessageMixin, CreateView):
    model = Currency
    form_class = CurrencyForm
    template_name = "catalog/currency/form.html"
    success_url = reverse_lazy("settings:currency_list")
    success_message = "Currency created."


class CurrencyUpdateView(LoginRequiredMixin, StaffRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    model = Currency
    form_class = CurrencyForm
    template_name = "catalog/currency/form.html"
    success_url = reverse_lazy("settings:currency_list")
    success_message = "Currency updated."


# ---------------------------------------------------------------------------
# Company Settings
# ---------------------------------------------------------------------------
COUNTRY_CHOICES = [
    ("SA", "Saudi Arabia"), ("AE", "United Arab Emirates"), ("EG", "Egypt"),
    ("KW", "Kuwait"), ("QA", "Qatar"), ("BH", "Bahrain"), ("OM", "Oman"),
    ("JO", "Jordan"), ("LB", "Lebanon"), ("IQ", "Iraq"),
    ("US", "United States"), ("GB", "United Kingdom"),
]

TIMEZONE_CHOICES = [
    ("Asia/Riyadh",   "Asia/Riyadh (Saudi Arabia)"),
    ("Asia/Dubai",    "Asia/Dubai (UAE)"),
    ("Africa/Cairo",  "Africa/Cairo (Egypt)"),
    ("Asia/Kuwait",   "Asia/Kuwait"),
    ("Asia/Qatar",    "Asia/Qatar"),
    ("Asia/Bahrain",  "Asia/Bahrain"),
    ("Asia/Muscat",   "Asia/Muscat (Oman)"),
    ("Asia/Amman",    "Asia/Amman (Jordan)"),
    ("Asia/Beirut",   "Asia/Beirut (Lebanon)"),
    ("Asia/Baghdad",  "Asia/Baghdad (Iraq)"),
    ("America/New_York", "America/New_York"),
    ("Europe/London", "Europe/London"),
    ("UTC",           "UTC"),
]

LANGUAGE_CHOICES = [("ar", "Arabic (العربية)"), ("en", "English")]

CURRENCY_CHOICES = [
    ("SAR", "Saudi Riyal (SAR)"), ("AED", "UAE Dirham (AED)"),
    ("EGP", "Egyptian Pound (EGP)"), ("KWD", "Kuwaiti Dinar (KWD)"),
    ("QAR", "Qatari Riyal (QAR)"), ("BHD", "Bahraini Dinar (BHD)"),
    ("OMR", "Omani Rial (OMR)"), ("JOD", "Jordanian Dinar (JOD)"),
    ("USD", "US Dollar (USD)"), ("GBP", "British Pound (GBP)"),
    ("EUR", "Euro (EUR)"),
]


class CompanySettingsForm(BootstrapFormMixin, forms.ModelForm):
    country = forms.ChoiceField(choices=COUNTRY_CHOICES)
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES)
    default_currency_code = forms.ChoiceField(choices=CURRENCY_CHOICES, label="Default Currency")

    class Meta:
        model = Organization
        fields = ["name", "legal_name", "code", "country", "timezone", "language", "default_currency_code"]
        labels = {
            "name": "Company Name",
            "legal_name": "Legal Name",
            "code": "Short Code",
        }


class CompanySettingsView(LoginRequiredMixin, StaffRequiredMixin, View):
    template_name = "settings/company.html"

    def _get_org(self, request):
        ctx = tenant_context.current()
        if ctx:
            return get_object_or_404(Organization, pk=ctx.organization_id)
        # Fallback for superusers without tenant context
        member = request.user.memberships.filter(role="admin", is_active=True).first()
        if member:
            return member.organization
        return None

    def get(self, request):
        org = self._get_org(request)
        if not org:
            messages.error(request, "No company found for your account.")
            return redirect("dashboard:home")
        form = CompanySettingsForm(instance=org)
        return render(request, self.template_name, {"form": form, "org": org})


# ---------------------------------------------------------------------------
# Mail Settings (legacy parity)
# ---------------------------------------------------------------------------
class MailSettingsForm(BootstrapFormMixin, forms.Form):
    mail_host = forms.CharField(label="Mail Host", required=True)
    port = forms.IntegerField(label="Mail Port", required=True, min_value=1, max_value=65535)
    mail_address = forms.EmailField(label="Mail Address", required=True)
    mail_name = forms.CharField(label="Mail From Name", required=True)
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to keep the current password.",
    )
    encryption = forms.ChoiceField(
        label="Encryption",
        choices=[("tls", "TLS"), ("ssl", "SSL"), ("none", "None")],
        required=True,
    )

    def __init__(self, *args, org: Organization | None = None, **kwargs):
        self.org = org
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        value = (self.cleaned_data.get("password") or "").strip()
        if value:
            return value
        if self.org and self.org.email_host_password:
            return ""
        raise forms.ValidationError("Password is required.")


def _smtp_connection_kwargs(org: Organization) -> dict:
    encryption = (org.email_encryption or "").strip().lower() or "tls"
    return {
        "host": (org.email_host or "").strip(),
        "port": int(org.email_port or 0) or 587,
        "username": (org.email_host_user or "").strip(),
        "password": (org.email_host_password or "").strip(),
        "use_tls": encryption == "tls",
        "use_ssl": encryption == "ssl",
        "timeout": 10,
    }


def _format_from_email(org: Organization) -> str:
    address = (org.email_from_address or "").strip() or settings.DEFAULT_FROM_EMAIL
    name = (org.email_from_name or "").strip()
    return f"{name} <{address}>" if name else address


class MailSettingsView(LoginRequiredMixin, StaffRequiredMixin, View):
    template_name = "settings/mail_setting.html"

    def _get_org(self, request):
        ctx = tenant_context.current()
        if ctx:
            return get_object_or_404(Organization, pk=ctx.organization_id)
        member = request.user.memberships.filter(role="admin", is_active=True).first()
        if member:
            return member.organization
        return None

    def get(self, request):
        org = self._get_org(request)
        if not org:
            messages.error(request, "No company found for your account.")
            return redirect("dashboard:home")

        form = MailSettingsForm(
            org=org,
            initial={
                "mail_host": org.email_host,
                "port": org.email_port,
                "mail_address": org.email_from_address,
                "mail_name": org.email_from_name,
                "encryption": (org.email_encryption or "tls").lower(),
            },
        )
        return render(request, self.template_name, {"form": form, "org": org})

    def post(self, request):
        from django.core.mail import EmailMessage, get_connection

        org = self._get_org(request)
        if not org:
            return redirect("dashboard:home")

        form = MailSettingsForm(request.POST, org=org)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "org": org})

        org.email_host = form.cleaned_data["mail_host"].strip()
        org.email_port = int(form.cleaned_data["port"])
        org.email_encryption = form.cleaned_data["encryption"]
        org.email_from_address = form.cleaned_data["mail_address"].strip()
        org.email_from_name = form.cleaned_data["mail_name"].strip()
        # Legacy UX: use the "mail address" as the SMTP username by default.
        org.email_host_user = org.email_from_address
        password = (form.cleaned_data.get("password") or "").strip()
        if password:
            org.email_host_password = password
        org.save()

        action = (request.POST.get("action") or "save").lower()
        if action == "test":
            if not org.email_host:
                messages.error(request, "Mail host is empty. Please save your mail settings first.")
                return redirect("settings:mail")
            try:
                conn = get_connection(**_smtp_connection_kwargs(org))
                msg = EmailMessage(
                    subject="GS ERP test email",
                    body="This is a test email from GS ERP.",
                    from_email=_format_from_email(org),
                    to=[request.user.email],
                    connection=conn,
                )
                msg.send(fail_silently=False)
                messages.success(request, f"Test email sent to {request.user.email}.")
            except Exception as exc:
                messages.error(request, f"Could not send test email: {exc}")
                return redirect("settings:mail")

        messages.success(request, "Mail settings saved successfully.")
        return redirect("settings:mail")


# ---------------------------------------------------------------------------
# SMS Settings + Create SMS (legacy parity)
# ---------------------------------------------------------------------------
class SMSSettingsForm(BootstrapFormMixin, forms.Form):
    gateway = forms.ChoiceField(
        label="Gateway",
        choices=[("", "Select SMS gateway..."), ("twilio", "Twilio"), ("clickatell", "Clickatell")],
        required=True,
    )
    account_sid = forms.CharField(label="ACCOUNT SID", required=False)
    auth_token = forms.CharField(label="AUTH TOKEN", required=False, widget=forms.PasswordInput(render_value=False))
    twilio_number = forms.CharField(label="Twilio Number", required=False)
    api_key = forms.CharField(label="API Key", required=False, widget=forms.PasswordInput(render_value=False))

    def __init__(self, *args, org: Organization | None = None, **kwargs):
        self.org = org
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        gateway = (cleaned.get("gateway") or "").strip()
        if gateway not in ("twilio", "clickatell"):
            raise forms.ValidationError("Select an SMS gateway.")

        if gateway == "twilio":
            have_existing = bool(self.org and self.org.twilio_account_sid and self.org.twilio_auth_token and self.org.twilio_number)
            sid = (cleaned.get("account_sid") or "").strip()
            token = (cleaned.get("auth_token") or "").strip()
            number = (cleaned.get("twilio_number") or "").strip()
            if not (sid and token and number) and not have_existing:
                raise forms.ValidationError("Twilio settings are incomplete.")

        if gateway == "clickatell":
            have_existing = bool(self.org and self.org.clickatell_api_key)
            key = (cleaned.get("api_key") or "").strip()
            if not key and not have_existing:
                raise forms.ValidationError("Clickatell API key is required.")

        return cleaned


class SMSSettingsView(LoginRequiredMixin, StaffRequiredMixin, View):
    template_name = "settings/sms_setting.html"

    def _get_org(self, request):
        ctx = tenant_context.current()
        if ctx:
            return get_object_or_404(Organization, pk=ctx.organization_id)
        member = request.user.memberships.filter(role="admin", is_active=True).first()
        if member:
            return member.organization
        return None

    def get(self, request):
        org = self._get_org(request)
        if not org:
            messages.error(request, "No company found for your account.")
            return redirect("dashboard:home")

        form = SMSSettingsForm(
            org=org,
            initial={
                "gateway": org.sms_gateway,
                "account_sid": org.twilio_account_sid,
                "twilio_number": org.twilio_number,
            },
        )
        return render(request, self.template_name, {"form": form, "org": org})

    def post(self, request):
        org = self._get_org(request)
        if not org:
            return redirect("dashboard:home")

        form = SMSSettingsForm(request.POST, org=org)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "org": org})

        gateway = form.cleaned_data["gateway"]
        org.sms_gateway = gateway

        if gateway == "twilio":
            sid = (form.cleaned_data.get("account_sid") or "").strip()
            token = (form.cleaned_data.get("auth_token") or "").strip()
            number = (form.cleaned_data.get("twilio_number") or "").strip()
            if sid:
                org.twilio_account_sid = sid
            if token:
                org.twilio_auth_token = token
            if number:
                org.twilio_number = number
        elif gateway == "clickatell":
            key = (form.cleaned_data.get("api_key") or "").strip()
            if key:
                org.clickatell_api_key = key

        org.save()
        messages.success(request, "SMS settings saved successfully.")
        return redirect("settings:sms")


class CreateSMSForm(BootstrapFormMixin, forms.Form):
    customers = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label="Customers",
        widget=forms.SelectMultiple(attrs={"size": 10}),
        help_text="Optional: select customers to auto-fill their mobile numbers.",
    )
    mobile = forms.CharField(
        label="Mobile",
        required=False,
        help_text="Comma-separated, e.g. +9665XXXXXXXX,+2010XXXXXXXX",
    )
    message = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 3}), required=True)

    def __init__(self, *args, **kwargs):
        from apps.crm.infrastructure.models import Customer

        super().__init__(*args, **kwargs)
        self.fields["customers"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        self.fields["customers"].widget.attrs.setdefault("class", "selectpicker")
        self.fields["customers"].widget.attrs.setdefault("data-live-search", "true")
        self.fields["customers"].widget.attrs.setdefault("multiple", "multiple")

    def clean(self):
        cleaned = super().clean()
        customers = cleaned.get("customers")
        mobile_raw = (cleaned.get("mobile") or "").strip()
        if not customers and not mobile_raw:
            raise forms.ValidationError("Select customers or enter mobile numbers.")
        return cleaned


def _send_sms_twilio(*, account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> None:
    import base64
    import urllib.parse
    import urllib.request

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = urllib.parse.urlencode({"From": from_number, "To": to_number, "Body": body}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    token = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        if resp.status >= 400:
            raise RuntimeError(f"Twilio HTTP {resp.status}")


def _send_sms_clickatell(*, api_key: str, to_number: str, body: str) -> None:
    import urllib.parse
    import urllib.request

    # Clickatell HTTP API (legacy-compatible): https://platform.clickatell.com/messages/http/send
    params = urllib.parse.urlencode({"apiKey": api_key, "to": to_number, "content": body})
    url = f"https://platform.clickatell.com/messages/http/send?{params}"
    with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
        if resp.status >= 400:
            raise RuntimeError(f"Clickatell HTTP {resp.status}")


class CreateSMSView(LoginRequiredMixin, StaffRequiredMixin, View):
    template_name = "settings/create_sms.html"

    def _get_org(self, request):
        ctx = tenant_context.current()
        if ctx:
            return get_object_or_404(Organization, pk=ctx.organization_id)
        member = request.user.memberships.filter(role="admin", is_active=True).first()
        if member:
            return member.organization
        return None

    def get(self, request):
        org = self._get_org(request)
        if not org:
            messages.error(request, "No company found for your account.")
            return redirect("dashboard:home")
        form = CreateSMSForm()
        return render(request, self.template_name, {"form": form, "org": org})

    def post(self, request):
        from apps.crm.infrastructure.models import Customer

        org = self._get_org(request)
        if not org:
            return redirect("dashboard:home")

        form = CreateSMSForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "org": org})

        gateway = (org.sms_gateway or "").strip().lower()
        if gateway not in ("twilio", "clickatell"):
            messages.error(request, "Please setup your SMS Setting first.")
            return redirect("settings:sms")

        numbers: list[str] = []
        customers = form.cleaned_data.get("customers") or Customer.objects.none()
        for c in customers:
            if c.phone:
                numbers.append(c.phone)
        raw = (form.cleaned_data.get("mobile") or "").strip()
        if raw:
            numbers.extend([n.strip() for n in raw.split(",") if n.strip()])
        # De-dup while preserving order
        seen: set[str] = set()
        numbers = [n for n in numbers if not (n in seen or seen.add(n))]

        body = form.cleaned_data["message"]
        try:
            if gateway == "twilio":
                sid = (org.twilio_account_sid or "").strip()
                token = (org.twilio_auth_token or "").strip()
                from_number = (org.twilio_number or "").strip()
                if not (sid and token and from_number):
                    messages.error(request, "Twilio settings are incomplete. Please update SMS settings.")
                    return redirect("settings:sms")
                for n in numbers:
                    _send_sms_twilio(account_sid=sid, auth_token=token, from_number=from_number, to_number=n, body=body)
            else:
                api_key = (org.clickatell_api_key or "").strip()
                if not api_key:
                    messages.error(request, "Clickatell settings are incomplete. Please update SMS settings.")
                    return redirect("settings:sms")
                for n in numbers:
                    _send_sms_clickatell(api_key=api_key, to_number=n, body=body)
        except Exception as exc:
            messages.error(request, f"Could not send SMS: {exc}")
            return redirect("settings:create_sms")

        messages.success(request, "SMS sent successfully.")
        return redirect("settings:create_sms")

    def post(self, request):
        org = self._get_org(request)
        if not org:
            return redirect("dashboard:home")
        form = CompanySettingsForm(request.POST, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Company settings saved successfully.")
            return redirect("settings:company")
        return render(request, self.template_name, {"form": form, "org": org})
