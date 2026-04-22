"""
Users web views.

Covers three entities:
  - User (auth.User via custom model): create/edit/list with password set.
  - Role (Django Group): create/edit/list with permission multi-select.
  - Profile: self-service read-only view of the current user.
  - Register: self-service company registration (creates User + Org + Subscription).

All admin CRUD views are gated via StaffRequiredMixin. Regular users
hit the Profile route (login-only) or the public Register route.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from django import forms
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, Permission
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView, View
from django.contrib import messages as django_messages

from common.forms import BootstrapFormMixin


User = get_user_model()


class StaffRequiredMixin(UserPassesTestMixin):
    """Gate admin pages to staff users, superusers, and org admins."""

    def test_func(self) -> bool:
        u = self.request.user  # type: ignore[attr-defined]
        if not u.is_authenticated:
            return False
        if u.is_staff or u.is_superuser:
            return True
        return u.memberships.filter(role="admin", is_active=True).exists()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------
class UserForm(BootstrapFormMixin, forms.ModelForm):
    """
    User create/edit form with optional password setting.

    Keeping password handling in this single form (rather than a separate
    "set password" view) matches the legacy UX and avoids a two-step dance
    for admins creating new users.
    """
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="New password",
        min_length=10,
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "is_active", "is_staff", "groups"]

    def save(self, commit: bool = True):
        user: User = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            user.set_password(password)
        elif not user.pk:
            # New user without password: make it unusable until first reset.
            user.set_unusable_password()
        if commit:
            user.save()
            self.save_m2m()
        return user


# ---------------------------------------------------------------------------
# Tenant-scoped User CRUD
# ---------------------------------------------------------------------------

ORG_ROLE_CHOICES = [
    ("admin",   "Administrator — full access"),
    ("manager", "Manager — can manage most resources"),
    ("staff",   "Staff — standard access"),
    ("viewer",  "Viewer — read-only"),
]


class TenantUserForm(BootstrapFormMixin, forms.ModelForm):
    """Create / edit a user within the current organisation."""

    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Password",
        min_length=8,
    )
    org_role = forms.ChoiceField(
        choices=ORG_ROLE_CHOICES,
        label="Role in this company",
        initial="staff",
    )
    branch = forms.ModelChoiceField(
        queryset=None,   # set in __init__
        required=False,
        label="Branch",
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "is_active"]

    def __init__(self, *args, org=None, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.tenancy.infrastructure.models import Branch
        self.org = org
        self.member = member
        # Branch choices scoped to the current org
        self.fields["branch"].queryset = (
            Branch.objects.filter(organization=org, is_active=True) if org else Branch.objects.none()
        )
        # Pre-fill role/branch from existing membership
        if member:
            self.fields["org_role"].initial = member.role
            self.fields["branch"].initial = member.branch_id

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("new_password")
        if pw:
            user.set_password(pw)
        elif not user.pk:
            user.set_unusable_password()
        role = self.cleaned_data.get("org_role", "staff")
        # Admins need is_staff so Django staff-gated views work
        user.is_staff = (role == "admin")
        if commit:
            user.save()
        return user

    def save_membership(self, user):
        from apps.users.infrastructure.models import OrganizationMember
        role = self.cleaned_data.get("org_role", "staff")
        branch = self.cleaned_data.get("branch")
        if self.member:
            self.member.role = role
            self.member.branch = branch
            self.member.save(update_fields=["role", "branch_id"])
        else:
            OrganizationMember.objects.get_or_create(
                user=user,
                organization=self.org,
                defaults={"role": role, "branch": branch, "is_active": True},
            )


def _current_org(request):
    """Return the Organisation the current request is operating under."""
    from apps.tenancy.domain import context as tenant_context
    from apps.tenancy.infrastructure.models import Organization
    ctx = tenant_context.current()
    if ctx:
        try:
            return Organization.objects.get(pk=ctx.organization_id)
        except Organization.DoesNotExist:
            pass
    # Fallback for superusers without tenant context
    member = request.user.memberships.filter(role="admin", is_active=True).first()
    return member.organization if member else None


class UserListView(StaffRequiredMixin, ListView):
    template_name = "users/user_list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        from apps.users.infrastructure.models import OrganizationMember
        org = _current_org(self.request)
        if not org:
            return User.objects.none()
        # Return users who belong to this org, annotated with their role
        return (
            User.objects
            .filter(memberships__organization=org, memberships__is_active=True)
            .distinct()
            .order_by("email")
        )

    def get_context_data(self, **kwargs):
        from apps.users.infrastructure.models import OrganizationMember
        ctx = super().get_context_data(**kwargs)
        org = _current_org(self.request)
        # Build a {user_id: member} map for role/branch display
        if org:
            ctx["memberships"] = {
                m.user_id: m
                for m in OrganizationMember.objects.filter(
                    organization=org, is_active=True
                ).select_related("branch")
            }
        else:
            ctx["memberships"] = {}
        ctx["org"] = org
        return ctx


class UserCreateView(StaffRequiredMixin, View):
    template_name = "users/user_form.html"

    def _form(self, request, data=None):
        org = _current_org(request)
        return TenantUserForm(data, org=org), org

    def get(self, request):
        form, org = self._form(request)
        return render(request, self.template_name, {"form": form, "org": org})

    def post(self, request):
        form, org = self._form(request, request.POST)
        if form.is_valid():
            user = form.save(commit=True)
            form.save_membership(user)
            from django.contrib import messages as msg
            msg.success(request, f"User {user.email} created and added to {org.name}.")
            return redirect("users:user_list")
        return render(request, self.template_name, {"form": form, "org": org})


class UserUpdateView(StaffRequiredMixin, View):
    template_name = "users/user_form.html"

    def _get_user_and_member(self, request, pk):
        from apps.users.infrastructure.models import OrganizationMember
        from django.http import Http404
        user = get_object_or_404(User, pk=pk)
        org = _current_org(request)
        member = OrganizationMember.objects.filter(
            user=user, organization=org, is_active=True
        ).first()
        if not member and not request.user.is_superuser:
            raise Http404("User not in your organisation.")
        return user, org, member

    def get(self, request, pk):
        user, org, member = self._get_user_and_member(request, pk)
        form = TenantUserForm(instance=user, org=org, member=member)
        return render(request, self.template_name, {"form": form, "object": user, "org": org})

    def post(self, request, pk):
        user, org, member = self._get_user_and_member(request, pk)
        form = TenantUserForm(request.POST, instance=user, org=org, member=member)
        if form.is_valid():
            form.save(commit=True)
            form.save_membership(user)
            from django.contrib import messages as msg
            msg.success(request, "User updated.")
            return redirect("users:user_list")
        return render(request, self.template_name, {"form": form, "object": user, "org": org})


# ---------------------------------------------------------------------------
# Role (Group) CRUD
# ---------------------------------------------------------------------------
class RoleForm(BootstrapFormMixin, forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "codename",
        ),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 18}),
    )

    class Meta:
        model = Group
        fields = ["name", "permissions"]


class RoleListView(StaffRequiredMixin, ListView):
    model = Group
    template_name = "users/role_list.html"
    context_object_name = "object_list"
    ordering = "name"


class RoleCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Group
    form_class = RoleForm
    template_name = "users/role_form.html"
    success_url = reverse_lazy("users:role_list")
    success_message = "Role created."


class RoleUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Group
    form_class = RoleForm
    template_name = "users/role_form.html"
    success_url = reverse_lazy("users:role_list")
    success_message = "Role updated."


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["memberships"] = (
            self.request.user.memberships
            .select_related("organization", "branch")
            .all()
            if self.request.user.is_authenticated
            else []
        )
        return ctx


# ---------------------------------------------------------------------------
# Company Registration (self-service onboarding)
# ---------------------------------------------------------------------------
class CompanyRegistrationForm(forms.Form):
    # Personal details
    first_name = forms.CharField(max_length=64, label="First Name")
    last_name = forms.CharField(max_length=64, label="Last Name")
    email = forms.EmailField(label="Work Email")
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm Password",
    )

    # Company details
    company_name = forms.CharField(max_length=128, label="Company Name")
    country = forms.ChoiceField(
        choices=[
            ("SA", "Saudi Arabia"),
            ("AE", "United Arab Emirates"),
            ("EG", "Egypt"),
            ("KW", "Kuwait"),
            ("QA", "Qatar"),
            ("BH", "Bahrain"),
            ("OM", "Oman"),
            ("JO", "Jordan"),
            ("LB", "Lebanon"),
            ("IQ", "Iraq"),
            ("US", "United States"),
            ("GB", "United Kingdom"),
            ("OTHER", "Other"),
        ],
        initial="SA",
        label="Country",
    )
    currency = forms.ChoiceField(
        choices=[
            ("SAR", "Saudi Riyal (SAR)"),
            ("AED", "UAE Dirham (AED)"),
            ("EGP", "Egyptian Pound (EGP)"),
            ("KWD", "Kuwaiti Dinar (KWD)"),
            ("QAR", "Qatari Riyal (QAR)"),
            ("BHD", "Bahraini Dinar (BHD)"),
            ("OMR", "Omani Rial (OMR)"),
            ("JOD", "Jordanian Dinar (JOD)"),
            ("USD", "US Dollar (USD)"),
            ("GBP", "British Pound (GBP)"),
            ("EUR", "Euro (EUR)"),
        ],
        initial="SAR",
        label="Default Currency",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.Select):
                css = "form-control"
            elif isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            widget.attrs["class"] = (existing + " " + css).strip()

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        cpw = cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned

    def _make_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:60] or "company"

    def save(self) -> "User":
        from apps.billing.infrastructure.models import Plan, Subscription
        from apps.tenancy.infrastructure.models import Branch, Organization
        from apps.users.infrastructure.models import OrganizationMember

        data = self.cleaned_data
        User = get_user_model()

        with transaction.atomic():
            # 1. Create user (is_staff=True so all staff-gated views work)
            user = User.objects.create_user(
                email=data["email"],
                password=data["password"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_staff=True,
            )

            # 2. Build a unique slug from company name
            base_slug = self._make_slug(data["company_name"])
            slug = base_slug
            counter = 1
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Country code mapping
            country = data["country"]
            if country == "OTHER":
                country = "SA"  # fall back to SA

            # 3. Create organization
            org = Organization.objects.create(
                name=data["company_name"],
                slug=slug,
                country=country,
                default_currency_code=data["currency"],
                language="en",
                timezone="Asia/Riyadh",
                is_active=True,
            )

            # 4. Create default branch
            Branch.objects.create(
                organization=org,
                name="Main Branch",
                code="MAIN",
                is_active=True,
            )

            # 5. Link user to org as owner
            OrganizationMember.objects.create(
                user=user,
                organization=org,
                role="admin",
                is_active=True,
            )

            # 6. Ensure a trial plan exists, then create subscription
            plan, _ = Plan.objects.get_or_create(
                code="trial",
                defaults={
                    "name": "Free Trial",
                    "duration_days": 30,
                    "price_minor_units": 0,
                    "currency_code": data["currency"],
                    "is_active": True,
                },
            )
            now = datetime.now(timezone.utc)
            Subscription.objects.create(
                organization=org,
                plan=plan,
                period_start=now,
                period_end=now + timedelta(days=30),
                is_cancelled=False,
                is_suspended=False,
            )

        return user


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    context_object_name = "object_list"
    paginate_by = 30

    def get_queryset(self):
        from apps.notifications.infrastructure.models import Notification
        return Notification.objects.all_tenants().filter(
            recipient=self.request.user
        ).order_by("-id")


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        from apps.notifications.infrastructure.models import Notification
        Notification.objects.all_tenants().filter(
            recipient=request.user,
            status__in=["pending", "sent"],
        ).update(status="read")
        django_messages.success(request, "All notifications marked as read.")
        return redirect("users:notifications")


class RegisterView(View):
    template_name = "auth/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, self.template_name, {"form": CompanyRegistrationForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        form = CompanyRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Authenticate and log in
            authenticated_user = authenticate(
                request, username=user.email, password=form.cleaned_data["password"]
            )
            if authenticated_user:
                login(request, authenticated_user)
            return redirect("dashboard:home")
        return render(request, self.template_name, {"form": form})
