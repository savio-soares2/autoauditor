"""
urls.py  –  Roteamento da API AutoAuditor
------------------------------------------
Inclua no urls.py do projeto host:

    from django.urls import path, include

    urlpatterns = [
        ...
        path("autoauditor/", include("autoauditor.urls")),
    ]

Rotas disponíveis:
    GET   /autoauditor/api/status/              – health-check + ferramentas + db counts
    POST  /autoauditor/api/audit/django/        – bandit (salva SecurityAudit)
    POST  /autoauditor/api/audit/frontend/      – npm audit (salva SecurityAudit)
    POST  /autoauditor/api/generate/test/       – prompt IA via AST
    POST  /autoauditor/api/run/tests/           – Pytest / Vitest / Playwright
    GET   /autoauditor/api/history/tests/       – histórico de TestRun
    GET   /autoauditor/api/history/security/    – histórico de SecurityAudit
    GET   /autoauditor/api/health/              – health score atual + histórico
    POST  /autoauditor/api/health/              – forçar recálculo do health score
    GET   /autoauditor/api/coverage/matrix/     – matriz de cobertura de testes
"""

from django.urls import path

from .views import (
    AuditDjangoView,
    AuditFrontendView,
    CacheAuditView,
    CoverageMatrixView,
    GenerateBatchView,
    GenerateTestView,
    ProjectHealthView,
    RunTestsView,
    RunTestsStreamView,
    SecurityHistoryView,
    StatusView,
    TestHistoryView,
)

app_name = "autoauditor"

urlpatterns = [
    # ── Health-check ──────────────────────────────────────────────────────────
    path("api/status/", StatusView.as_view(), name="status"),

    # ── Auditorias de Segurança ───────────────────────────────────────────────
    path("api/audit/django/",   AuditDjangoView.as_view(),   name="audit-django"),
    path("api/audit/frontend/", AuditFrontendView.as_view(), name="audit-frontend"),

    # ── Auditoria de Cache (estática AST + probe dinâmico) ────────────────────
    path("api/audit/cache/",    CacheAuditView.as_view(),    name="audit-cache"),

    # ── Geração de Testes via AST ─────────────────────────────────────────────
    path("api/generate/test/",  GenerateTestView.as_view(),  name="generate-test"),
    path("api/generate/batch/", GenerateBatchView.as_view(), name="generate-batch"),

    # ── Executores de Testes (Pytest / Vitest / Playwright) ─────────────────────
    path("api/run/tests/",  RunTestsView.as_view(),       name="run-tests"),
    path("api/run/stream/", RunTestsStreamView.as_view(), name="run-stream"),

    # ── Histórico ─────────────────────────────────────────────────────────────
    path("api/history/tests/",    TestHistoryView.as_view(),     name="history-tests"),
    path("api/history/security/", SecurityHistoryView.as_view(), name="history-security"),

    # ── Health Score & Coverage ───────────────────────────────────────────────
    path("api/health/",           ProjectHealthView.as_view(),  name="health"),
    path("api/coverage/matrix/",  CoverageMatrixView.as_view(), name="coverage-matrix"),
]
