"""
models.py  –  Persistência de Resultados do AutoAuditor
---------------------------------------------------------
Três models principais:

  TestRun        – Resultado de uma execução de Pytest / Vitest / Playwright
  SecurityAudit  – Resultado de uma auditoria Bandit / npm audit
  ProjectHealth  – Snapshot agregado de saúde calculado após cada execução

Para registrar as migrations no projeto host:
    python manage.py makemigrations autoauditor
    python manage.py migrate
"""

from django.db import models
from django.utils import timezone


# ── TestRun ────────────────────────────────────────────────────────────────────

class TestRun(models.Model):
    """
    Armazena o resultado consolidado de uma execução de suite de testes.
    O campo `raw_report` guarda o JSON completo retornado pela ferramenta.
    """

    class RunType(models.TextChoices):
        PYTEST      = "pytest",     "Pytest (Django)"
        VITEST      = "vitest",     "Vitest (React)"
        PLAYWRIGHT  = "playwright", "Playwright (E2E)"

    run_type        = models.CharField(max_length=20, choices=RunType.choices, db_index=True)
    created_at      = models.DateTimeField(default=timezone.now, db_index=True)

    # ── Totais ──────────────────────────────────────────────────
    total           = models.IntegerField(default=0)
    passed          = models.IntegerField(default=0)
    failed          = models.IntegerField(default=0)
    errors          = models.IntegerField(default=0)
    skipped         = models.IntegerField(default=0)
    duration_seconds = models.FloatField(default=0.0)

    # ── Relatório bruto ─────────────────────────────────────────
    raw_report      = models.JSONField(default=dict)

    # ── Metadados opcionais ─────────────────────────────────────
    target_path     = models.TextField(blank=True, default="")
    exit_code       = models.IntegerField(default=0)
    stderr_output   = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Test Run"
        verbose_name_plural = "Test Runs"

    def __str__(self) -> str:
        return f"[{self.run_type}] {self.created_at:%Y-%m-%d %H:%M} – {self.passed}/{self.total} passed"

    @property
    def pass_rate(self) -> float:
        """Percentual de testes que passaram (0.0 – 100.0)."""
        if self.total == 0:
            return 0.0
        return round(self.passed / self.total * 100, 1)

    @property
    def has_failures(self) -> bool:
        return (self.failed + self.errors) > 0


# ── SecurityAudit ──────────────────────────────────────────────────────────────

class SecurityAudit(models.Model):
    """
    Armazena o resultado consolidado de uma auditoria de segurança.
    Funciona para Bandit (Python) e npm audit (Node/React).
    """

    class Tool(models.TextChoices):
        BANDIT    = "bandit",    "Bandit (Python)"
        NPM_AUDIT = "npm_audit", "npm audit (Node)"

    tool       = models.CharField(max_length=20, choices=Tool.choices, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    # ── Contagem por severidade ─────────────────────────────────
    info       = models.IntegerField(default=0)
    low        = models.IntegerField(default=0)
    medium     = models.IntegerField(default=0)
    high       = models.IntegerField(default=0)
    critical   = models.IntegerField(default=0)

    # ── Relatório bruto ─────────────────────────────────────────
    raw_report = models.JSONField(default=dict)
    target_path = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Security Audit"
        verbose_name_plural = "Security Audits"

    def __str__(self) -> str:
        return f"[{self.tool}] {self.created_at:%Y-%m-%d %H:%M} – H:{self.high} C:{self.critical}"

    @property
    def total_vulnerabilities(self) -> int:
        return self.info + self.low + self.medium + self.high + self.critical

    @property
    def security_score(self) -> float:
        """
        Nota de segurança de 0 a 100.
        Penalidades: critical×25, high×10, medium×4, low×1.
        """
        penalty = (
            self.critical * 25
            + self.high    * 10
            + self.medium  *  4
            + self.low     *  1
        )
        return max(0.0, round(100.0 - penalty, 1))


# ── ProjectHealth ──────────────────────────────────────────────────────────────

class ProjectHealth(models.Model):
    """
    Snapshot agregado de saúde do projeto, recalculado após cada execução.
    É o dado que alimenta o gráfico de tendência histórica.

    Formula do score (0–100):
        score = 0.6 × test_pass_rate + 0.4 × security_score
    """

    created_at       = models.DateTimeField(default=timezone.now, db_index=True)

    # ── Score composto ──────────────────────────────────────────
    score            = models.FloatField(default=0.0)   # 0–100

    # ── Componentes individuais ─────────────────────────────────
    test_pass_rate   = models.FloatField(default=0.0)   # % testes passando
    security_score   = models.FloatField(default=100.0) # nota de segurança

    # ── Contagens de testes por tipo ────────────────────────────
    pytest_passed    = models.IntegerField(default=0)
    pytest_total     = models.IntegerField(default=0)
    vitest_passed    = models.IntegerField(default=0)
    vitest_total     = models.IntegerField(default=0)
    playwright_passed = models.IntegerField(default=0)
    playwright_total  = models.IntegerField(default=0)

    # ── Arquivos sem cobertura ──────────────────────────────────
    uncovered_files  = models.JSONField(default=list)
    covered_count    = models.IntegerField(default=0)
    uncovered_count  = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Project Health Snapshot"
        verbose_name_plural = "Project Health Snapshots"

    def __str__(self) -> str:
        return f"Health {self.score:.1f}/100 @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def grade(self) -> str:
        """Converte score numérico em letra de avaliação."""
        if self.score >= 90:
            return "A"
        elif self.score >= 75:
            return "B"
        elif self.score >= 60:
            return "C"
        elif self.score >= 40:
            return "D"
        return "F"
