"""
Users infrastructure.

- `User`: custom user model with email as the natural identifier (no legacy
  `role_id` column — ADR-011).
- `OrganizationMember`: through-table binding a user to an organization with
  a role. A user may belong to multiple organizations; every tenant-scoped
  action resolves the active organization from this table via the tenancy
  middleware.
- `UserManager`: Django's auth manager tweaked for email-based accounts.

Roles are Django groups (ADR-011). The `role` column on `OrganizationMember`
records the group name granted within that organization so access control is
always scoped to the active tenant context.
"""
from __future__ import annotations

import secrets
import string
from datetime import timedelta
from typing import Any

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import Branch, Organization


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class UserManager(BaseUserManager["User"]):
    """Email-based user manager. No username field."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        validate_email(email)
        user: User = self.model(email=email, **extra_fields)
        user.password = make_password(password) if password else make_password(None)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    """
    Custom user identified by email.

    Multi-tenant membership lives in `OrganizationMember`; this table holds
    only the global identity + authentication fields. Tenant-scoped attributes
    (which branch a user primarily operates from, role within an org) belong
    on `OrganizationMember`, not here.
    """

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=64, blank=True, default="")
    last_name = models.CharField(max_length=64, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")

    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        db_table = "users_user"
        ordering = ("email",)

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# OrganizationMember
# ---------------------------------------------------------------------------
class OrganizationMember(TimestampedModel):
    """
    Membership of a `User` in an `Organization`.

    One row per (user, organization). Holds the role granted within that
    organization and an optional primary branch. Access control at runtime is:

        is_member(user, active_org)  AND  user.has_perm(codename_for_active_role)
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="members",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=64,
        help_text="Django group name granted to the user within this organization.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "users_organization_member"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"),
                name="users_member_unique_user_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.organization.name} ({self.role})"


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
class OTPCode(TimestampedModel):
    """One-time password for email-based login verification."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "users_otp_code"
        indexes = [models.Index(fields=("user", "is_used", "expires_at"))]

    @classmethod
    def generate_for(cls, user: "User", expiry_minutes: int = 10) -> "OTPCode":
        # Reuse an existing valid OTP that still has >1 minute of life.
        # This prevents double form submission or page refresh from invalidating
        # the code already sent to the user's inbox.
        still_valid = (
            cls.objects
            .filter(user=user, is_used=False, expires_at__gt=timezone.now() + timedelta(seconds=60))
            .order_by("-created_at")
            .first()
        )
        if still_valid:
            return still_valid

        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        code = "".join(secrets.choice(string.digits) for _ in range(6))
        return cls.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
        )

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    def consume(self) -> None:
        self.is_used = True
        self.save(update_fields=["is_used"])
