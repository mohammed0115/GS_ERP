"""
Users web views.

Covers three entities:
  - User (auth.User via custom model): create/edit/list with password set.
  - Role (Django Group): create/edit/list with permission multi-select.
  - Profile: self-service read-only view of the current user.

All of these are admin-gated via `PermissionRequiredMixin`. Regular users
hit the Profile route, which is login-only.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, Permission
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from common.forms import BootstrapFormMixin


User = get_user_model()


class StaffRequiredMixin(UserPassesTestMixin):
    """Gate admin pages to staff users. Superusers always pass."""

    def test_func(self) -> bool:
        u = self.request.user  # type: ignore[attr-defined]
        return bool(u.is_authenticated and (u.is_staff or u.is_superuser))


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


class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = "users/user_list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "email"


class UserCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = "users/user_form.html"
    success_url = reverse_lazy("users:user_list")
    success_message = "User created."


class UserUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = "users/user_form.html"
    success_url = reverse_lazy("users:user_list")
    success_message = "User updated."


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
