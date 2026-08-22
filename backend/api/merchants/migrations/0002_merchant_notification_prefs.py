from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("merchants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchant",
            name="notification_prefs",
            field=models.JSONField(
                default=dict,
                help_text=(
                    'Per-merchant notification preferences: '
                    '{"severity_threshold": "warning", "channels": ["in_app", "email"]}'
                ),
            ),
        ),
    ]
