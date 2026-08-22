import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0001_initial"),
        ("analytics", "0001_initial"),
        ("chat", "0001_initial"),
        ("merchants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
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
                ("channel", models.CharField(max_length=32)),
                ("status", models.CharField(max_length=32)),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField()),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "insight",
                    models.ForeignKey(
                        db_column="insight_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to="analytics.insight",
                    ),
                ),
                (
                    "merchant",
                    models.ForeignKey(
                        db_column="merchant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="merchants.merchant",
                    ),
                ),
            ],
            options={
                "db_table": "notification",
                "indexes": [
                    models.Index(
                        fields=["merchant", "status", "created_at"],
                        name="notif_mer_st_cr_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="CostLedgerEntry",
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
                ("scope", models.CharField(max_length=32)),
                ("amount_usd", models.DecimalField(decimal_places=6, max_digits=12)),
                ("ledger_date", models.DateField()),
                ("created_at", models.DateTimeField()),
                (
                    "agent_run_step",
                    models.ForeignKey(
                        blank=True,
                        db_column="agent_run_step_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cost_ledger_entries",
                        to="agent.agentrunstep",
                    ),
                ),
                (
                    "chat_turn_step",
                    models.ForeignKey(
                        blank=True,
                        db_column="chat_turn_step_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cost_ledger_entries",
                        to="chat.chatturnstep",
                    ),
                ),
                (
                    "merchant",
                    models.ForeignKey(
                        db_column="merchant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cost_ledger_entries",
                        to="merchants.merchant",
                    ),
                ),
                ("tier", models.CharField(default="cheap", max_length=32)),
                ("tokens_in", models.IntegerField(default=0)),
                ("tokens_out", models.IntegerField(default=0)),
            ],
            options={
                "db_table": "cost_ledger_entry",
                "indexes": [
                    models.Index(
                        fields=["scope", "merchant", "ledger_date"],
                        name="cle_scope_merchant_date_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        check=(
                            models.Q(
                                agent_run_step__isnull=True,
                                chat_turn_step__isnull=False,
                            )
                            | models.Q(
                                agent_run_step__isnull=False,
                                chat_turn_step__isnull=True,
                            )
                        ),
                        name="cle_one_fkey_chk",
                    ),
                    models.CheckConstraint(
                        check=(
                            models.Q(scope="agent") & models.Q(agent_run_step__isnull=False)
                            | models.Q(scope="chat") & models.Q(chat_turn_step__isnull=False)
                        ),
                        name="cle_scope_fkey_chk",
                    ),
                ],
            },
        ),
    ]
