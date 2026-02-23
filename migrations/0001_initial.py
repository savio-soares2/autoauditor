"""
Initial migration for the autoauditor app.
Generated for models: TestRun, SecurityAudit, ProjectHealth
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_type", models.CharField(
                    choices=[
                        ("pytest",     "Pytest (Django)"),
                        ("vitest",     "Vitest (React)"),
                        ("playwright", "Playwright (E2E)"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("total",            models.IntegerField(default=0)),
                ("passed",           models.IntegerField(default=0)),
                ("failed",           models.IntegerField(default=0)),
                ("errors",           models.IntegerField(default=0)),
                ("skipped",          models.IntegerField(default=0)),
                ("duration_seconds", models.FloatField(default=0.0)),
                ("raw_report",       models.JSONField(default=dict)),
                ("target_path",      models.TextField(blank=True, default="")),
                ("exit_code",        models.IntegerField(default=0)),
                ("stderr_output",    models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Test Run",
                "verbose_name_plural": "Test Runs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SecurityAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tool", models.CharField(
                    choices=[
                        ("bandit",    "Bandit (Python)"),
                        ("npm_audit", "npm audit (Node)"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("created_at",   models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("info",         models.IntegerField(default=0)),
                ("low",          models.IntegerField(default=0)),
                ("medium",       models.IntegerField(default=0)),
                ("high",         models.IntegerField(default=0)),
                ("critical",     models.IntegerField(default=0)),
                ("raw_report",   models.JSONField(default=dict)),
                ("target_path",  models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Security Audit",
                "verbose_name_plural": "Security Audits",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProjectHealth",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at",         models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("score",              models.FloatField(default=0.0)),
                ("test_pass_rate",     models.FloatField(default=0.0)),
                ("security_score",     models.FloatField(default=100.0)),
                ("pytest_passed",      models.IntegerField(default=0)),
                ("pytest_total",       models.IntegerField(default=0)),
                ("vitest_passed",      models.IntegerField(default=0)),
                ("vitest_total",       models.IntegerField(default=0)),
                ("playwright_passed",  models.IntegerField(default=0)),
                ("playwright_total",   models.IntegerField(default=0)),
                ("uncovered_files",    models.JSONField(default=list)),
                ("covered_count",      models.IntegerField(default=0)),
                ("uncovered_count",    models.IntegerField(default=0)),
            ],
            options={
                "verbose_name": "Project Health Snapshot",
                "verbose_name_plural": "Project Health Snapshots",
                "ordering": ["-created_at"],
            },
        ),
    ]
