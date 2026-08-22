import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("merchants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("status", models.CharField(max_length=32)),
                ("language_hint", models.CharField(default="fa", max_length=16)),
                ("started_at", models.DateTimeField()),
                ("last_activity_at", models.DateTimeField()),
                (
                    "merchant",
                    models.ForeignKey(
                        db_column="merchant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_sessions",
                        to="merchants.merchant",
                    ),
                ),
                (
                    "merchant_user",
                    models.ForeignKey(
                        db_column="merchant_user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_sessions",
                        to="merchants.merchantuser",
                    ),
                ),
            ],
            options={
                "db_table": "chat_session",
                "indexes": [
                    models.Index(
                        fields=["merchant", "last_activity_at"],
                        name="cs_mer_last_act_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("role", models.CharField(max_length=32)),
                ("content", models.TextField()),
                ("referenced_insight_ids", models.JSONField(default=list)),
                ("tokens_in", models.IntegerField(default=0)),
                ("tokens_out", models.IntegerField(default=0)),
                ("model_used", models.CharField(blank=True, max_length=128)),
                ("delivery_mode", models.CharField(default="buffered", max_length=32)),
                ("created_at", models.DateTimeField()),
                (
                    "session",
                    models.ForeignKey(
                        db_column="session_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="chat.chatsession",
                    ),
                ),
            ],
            options={
                "db_table": "chat_message",
                "indexes": [
                    models.Index(
                        fields=["session", "created_at"],
                        name="cm_session_created_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ChatTurnStep",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("step_name", models.CharField(max_length=128)),
                ("status", models.CharField(max_length=32)),
                ("checkpoint_state", models.JSONField(default=dict)),
                ("cost_usd", models.DecimalField(decimal_places=6, max_digits=12)),
                ("executed_at", models.DateTimeField()),
                (
                    "message",
                    models.ForeignKey(
                        db_column="message_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turn_steps",
                        to="chat.chatmessage",
                    ),
                ),
            ],
            options={
                "db_table": "chat_turn_step",
                "indexes": [
                    models.Index(fields=["message"], name="cts_message_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MerchantChatMemory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("summary_text", models.TextField()),
                ("key_facts", models.JSONField(default=list)),
                ("updated_at", models.DateTimeField()),
                (
                    "merchant",
                    models.ForeignKey(
                        db_column="merchant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_memories",
                        to="merchants.merchant",
                    ),
                ),
            ],
            options={
                "db_table": "merchant_chat_memory",
                "indexes": [
                    models.Index(
                        fields=["merchant", "period_start"],
                        name="mcm_mer_period_idx",
                    ),
                ],
            },
        ),
    ]
