"""
import_legacy_users.

Imports legacy `users` rows into the new `users_user` table and creates
`users_organization_member` rows binding each user to their legacy
`organization_id`.

Passwords: legacy stores bcrypt hashes that Django can consume unchanged
as long as they use the `bcrypt` prefix. Any other format is discarded
and the user gets an unusable password — they must reset at first login.
"""
from __future__ import annotations

from typing import Any

from apps.etl.models import lookup, remember
from apps.users.infrastructure.models import OrganizationMember, User
from common.etl.base import LegacyImportCommand, legacy_rows


def _usable_django_password(legacy_hash: str | None) -> str:
    """Convert legacy hashes to the Django `<algo>$...` format where possible."""
    if not legacy_hash:
        return ""  # unusable — user must reset
    # Laravel bcrypt: $2y$...  Django: bcrypt$$2b$...
    # The bcrypt library accepts $2y$ transparently, so we rewrite the prefix.
    if legacy_hash.startswith("$2y$") or legacy_hash.startswith("$2b$") or legacy_hash.startswith("$2a$"):
        return f"bcrypt_sha256${legacy_hash}" if False else f"bcrypt${legacy_hash}"
    return ""  # unknown — unusable


class Command(LegacyImportCommand):
    help = "Import legacy users into the new users_user + organization_member tables."
    required_tenant = False  # users are cross-tenant; we assign membership per user

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        user_count = 0
        member_count = 0
        skipped = 0

        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, email, password, phone, is_active, organization_id FROM users",
        ):
            legacy_id = int(row["id"])
            email = (row["email"] or "").strip().lower()
            if not email:
                skipped += 1
                continue

            name_parts = (row["name"] or "").strip().split(None, 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "first_name": first_name[:64],
                    "last_name": last_name[:64],
                    "phone": (row["phone"] or "")[:32],
                    "is_active": bool(row["is_active"]),
                },
            )
            legacy_hash = row.get("password")
            converted = _usable_django_password(legacy_hash)
            if converted:
                user.password = converted
            else:
                user.set_unusable_password()
            user.save(update_fields=["password"])

            remember(legacy_table="users", legacy_id=legacy_id, new_id=user.pk)
            user_count += 1

            # Membership
            legacy_org_id = row.get("organization_id")
            if legacy_org_id:
                new_org_id = lookup(
                    legacy_table="organizations",
                    legacy_id=int(legacy_org_id),
                )
                if new_org_id is None:
                    continue  # upstream tenancy import missing for this org
                OrganizationMember.objects.all_tenants().update_or_create(
                    user=user,
                    organization_id=new_org_id,
                    defaults={"role": "member", "is_active": bool(row["is_active"])},
                )
                member_count += 1

        stdout.write(f"  users: {user_count} (skipped: {skipped})  memberships: {member_count}")
        return {"users": user_count, "memberships": member_count, "skipped": skipped}
