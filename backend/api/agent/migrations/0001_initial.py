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
            name="AgentRun",
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
                ("workflow_id", models.CharField(max_length=128, unique=True)),
                ("status", models.CharField(max_length=32)),
                ("checkpoint_state", models.JSONField(default=dict)),
                ("tokens_used", models.IntegerField(default=0)),
                ("estimated_cost_usd", models.DecimalField(decimal_places=6, max_digits=12)),
                ("cost_ceiling_usd", models.DecimalField(decimal_places=6, max_digits=12)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "merchant",
                    models.ForeignKey(
                        db_column="merchant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_runs",
                        to="merchants.merchant",
                    ),
                ),
            ],
            options={"db_table": "agent_run"},
        ),
        migrations.CreateModel(
            name="AgentRunStep",
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
                ("input_snapshot", models.JSONField(default=dict)),
                ("output_snapshot", models.JSONField(default=dict)),
                ("model_used", models.CharField(max_length=128)),
                ("tokens_in", models.IntegerField(default=0)),
                ("tokens_out", models.IntegerField(default=0)),
                ("cost_usd", models.DecimalField(decimal_places=6, max_digits=12)),
                ("executed_at", models.DateTimeField()),
                (
                    "agent_run",
                    models.ForeignKey(
                        db_column="agent_run_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="agent.agentrun",
                    ),
                ),
            ],
            options={
                "db_table": "agent_run_step",
                "indexes": [
                    models.Index(
                        fields=["agent_run", "executed_at"],
                        name="ars_run_ts_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                (
                    "key",
                    models.CharField(max_length=128, primary_key=True, serialize=False),
                ),
                ("scope", models.CharField(max_length=64)),
                ("response_snapshot", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
            ],
            options={
                "db_table": "idempotency_key",
                "indexes": [
                    models.Index(
                        fields=["scope", "expires_at"],
                        name="idem_scope_exp_idx",
                    ),
                ],
            },
        ),
    ]
