"""
Notifications infrastructure.

`Notification` is a record targeted at a user (in-app). A Celery task picks
up unsent rows and dispatches via the configured channel (email, SMS). The
legacy system did this synchronously inside HTTP handlers; here it's async
with retry by default.
"""
from __future__ import annotations

from enum import Enum

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class ChannelChoices(models.TextChoices):
    IN_APP = NotificationChannel.IN_APP.value, "In-App"
    EMAIL = NotificationChannel.EMAIL.value, "Email"
    SMS = NotificationChannel.SMS.value, "SMS"


class StatusChoices(models.TextChoices):
    PENDING = NotificationStatus.PENDING.value, "Pending"
    SENT = NotificationStatus.SENT.value, "Sent"
    FAILED = NotificationStatus.FAILED.value, "Failed"
    READ = NotificationStatus.READ.value, "Read"


class Notification(TenantOwnedModel, TimestampedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(
        max_length=16, choices=ChannelChoices.choices,
        default=ChannelChoices.IN_APP, db_index=True,
    )
    status = models.CharField(
        max_length=16, choices=StatusChoices.choices,
        default=StatusChoices.PENDING, db_index=True,
    )

    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    # Soft-polymorphic reference to the originating entity.
    source_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id = models.BigIntegerField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "notifications_notification"
        ordering = ("-id",)
        indexes = [
            models.Index(fields=("organization", "recipient", "status")),
            models.Index(fields=("organization", "source_type", "source_id")),
        ]

    def __str__(self) -> str:
        return f"{self.channel}→{self.recipient_id} [{self.status}] {self.subject}"
