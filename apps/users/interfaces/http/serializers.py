"""Serializers for user-facing endpoints. Shape validation only."""
from __future__ import annotations

from rest_framework import serializers

from apps.users.infrastructure.models import OrganizationMember, User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    branch_id = serializers.IntegerField(source="branch.id", read_only=True, allow_null=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)

    class Meta:
        model = OrganizationMember
        fields = (
            "organization_id",
            "organization_name",
            "organization_slug",
            "branch_id",
            "branch_name",
            "role",
            "is_active",
        )


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    memberships = OrganizationMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "is_active",
            "memberships",
        )
