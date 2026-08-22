import uuid

from django.db import models


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category_key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)

    class Meta:
        db_table = "category"

    def __str__(self) -> str:
        return self.category_key


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_key = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="merchants",
        db_column="category_id",
    )
    is_active = models.BooleanField(default=True)
    notification_prefs = models.JSONField(
        default=dict,
        help_text=(
            "Per-merchant notification preferences: "
            '{"severity_threshold": "warning", "channels": ["in_app", "email"]}'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchant"

    def __str__(self) -> str:
        return self.merchant_key


class Terminal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    terminal_key = models.CharField(max_length=64, unique=True)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="terminals",
        db_column="merchant_id",
    )

    class Meta:
        db_table = "terminal"

    def __str__(self) -> str:
        return self.terminal_key


class MerchantUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="users",
        db_column="merchant_id",
    )
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=64)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merchant_user"
        indexes = [
            models.Index(
                fields=["locked_until"],
                name="merchant_user_locked_until_idx",
                condition=models.Q(locked_until__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return self.email


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_user = models.ForeignKey(
        MerchantUser,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_column="merchant_user_id",
    )
    action = models.CharField(max_length=128)
    metadata = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(
                fields=["merchant_user", "created_at"],
                name="audit_log_user_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.merchant_user_id})"


class EventCalendar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=128, unique=True)
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    event_type = models.CharField(max_length=64)

    class Meta:
        db_table = "event_calendar"
        indexes = [
            models.Index(
                fields=["start_date", "end_date"],
                name="event_calendar_date_range_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.event_key
