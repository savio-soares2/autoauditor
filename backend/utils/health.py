"""
utils/health.py  –  Cálculo do Health Score e Matriz de Cobertura
------------------------------------------------------------------
Funções puras (sem side-effects de banco) para:
  • Calcular o score de saúde a partir dos últimos TestRun e SecurityAudit
  • Varrer o sistema de arquivos e produzir a Matriz de Cobertura
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field


# ── Health Score ───────────────────────────────────────────────────────────────

@dataclass
class HealthResult:
    score: float
    test_pass_rate: float
    security_score: float
    pytest_passed: int
    pytest_total: int
    vitest_passed: int
    vitest_total: int
    playwright_passed: int
    playwright_total: int


def compute_health_score(
    test_runs: list,          # QuerySet ou list de TestRun
    security_audits: list,    # QuerySet ou list de SecurityAudit
) -> HealthResult:
    """
    Calcula o Health Score agregado do projeto.

    Peso:
        60 % – taxa de aprovação dos testes (média ponderada entre todas as suites)
        40 % – nota de segurança (média entre bandit e npm audit)
    """
    from .models import TestRun  # import local para evitar circular

    # ── Testes ────────────────────────────────────────────────────────────────
    # Pega o run mais recente de cada tipo
    runs_by_type: dict[str, object] = {}
    for run in test_runs:
        t = run.run_type
        if t not in runs_by_type:
            runs_by_type[t] = run

    def _stats(run_type: str) -> tuple[int, int]:
        r = runs_by_type.get(run_type)
        return (r.passed, r.total) if r else (0, 0)

    pytest_p, pytest_t          = _stats(TestRun.RunType.PYTEST)
    vitest_p, vitest_t          = _stats(TestRun.RunType.VITEST)
    playwright_p, playwright_t  = _stats(TestRun.RunType.PLAYWRIGHT)

    total_passed = pytest_p + vitest_p + playwright_p
    total_tests  = pytest_t + vitest_t + playwright_t

    if total_tests > 0:
        test_pass_rate = round(total_passed / total_tests * 100, 1)
    else:
        test_pass_rate = 0.0  # sem dados = penaliza levemente

    # ── Segurança ─────────────────────────────────────────────────────────────
    if security_audits:
        sec_scores = [a.security_score for a in security_audits]
        # Usa o pior (menor) score encontrado para não mascarar problemas
        security_score = round(min(sec_scores), 1)
    else:
        security_score = 100.0  # sem dados = assume limpo

    # ── Score Final ───────────────────────────────────────────────────────────
    score = round(0.6 * test_pass_rate + 0.4 * security_score, 1)

    return HealthResult(
        score=score,
        test_pass_rate=test_pass_rate,
        security_score=security_score,
        pytest_passed=pytest_p,
        pytest_total=pytest_t,
        vitest_passed=vitest_p,
        vitest_total=vitest_t,
        playwright_passed=playwright_p,
        playwright_total=playwright_t,
    )


# ── Coverage Matrix ────────────────────────────────────────────────────────────

@dataclass
class FileEntry:
    path: str         # caminho relativo ao root do projeto
    language: str     # "python" | "react"
    covered: bool     # True se existe arquivo de teste correspondente
    test_file: str    # caminho do arquivo de teste (ou "")


@dataclass
class CoverageMatrix:
    entries: list[FileEntry] = field(default_factory=list)

    @property
    def covered(self) -> list[FileEntry]:
        return [e for e in self.entries if e.covered]

    @property
    def uncovered(self) -> list[FileEntry]:
        return [e for e in self.entries if not e.covered]

    @property
    def coverage_pct(self) -> float:
        if not self.entries:
            return 0.0
        return round(len(self.covered) / len(self.entries) * 100, 1)


# Padrões de exclusão – não queremos auditar esses arquivos
_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    "migrations", "static", "staticfiles", "media", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".tox",
}

_EXCLUDE_PY_NAMES = {
    "__init__.py", "manage.py", "wsgi.py", "asgi.py",
    "settings.py", "conftest.py", "setup.py",
}


def _is_test_file(path: Path) -> bool:
    name = path.stem.lower()
    return name.startswith("test_") or name.endswith("_test") or name.endswith(".test") or name.endswith(".spec")


def _find_test_for_python(source: Path, all_py_files: set[Path]) -> str:
    """Dado um arquivo .py, procura um test_.py correspondente."""
    stem = source.stem
    candidates = [
        source.parent / f"test_{stem}.py",
        source.parent / "tests" / f"test_{stem}.py",
        source.parent.parent / "tests" / f"test_{stem}.py",
        source.parent / f"{stem}_test.py",
    ]
    for c in candidates:
        if c in all_py_files or c.exists():
            return str(c)
    return ""


def _find_test_for_jsx(source: Path, all_fe_files: set[Path]) -> str:
    """Dado um .jsx/.tsx, procura um .test.jsx ou .spec.jsx correspondente."""
    stem = source.stem
    suffix = source.suffix  # .jsx ou .tsx
    candidates = [
        source.parent / f"{stem}.test{suffix}",
        source.parent / f"{stem}.spec{suffix}",
        source.parent / "__tests__" / f"{stem}.test{suffix}",
        source.parent / "__tests__" / f"{stem}{suffix}",
    ]
    for c in candidates:
        if c in all_fe_files or c.exists():
            return str(c)
    return ""


def build_coverage_matrix(project_root: str | Path) -> CoverageMatrix:
    """
    Varre `project_root` e retorna a CoverageMatrix completa do projeto.
    """
    root = Path(project_root).resolve()
    matrix = CoverageMatrix()

    # ── Coleta todos os arquivos relevantes primeiro ───────────────────────────
    all_py:  set[Path] = set()
    all_fe:  set[Path] = set()  # jsx, tsx

    for dirpath, dirnames, filenames in os.walk(root):
        # Poda pastas excluídas in-place para os walk não entrar nelas
        dirnames[:] = [
            d for d in dirnames
            if d not in _EXCLUDE_DIRS and not d.startswith(".")
        ]
        p = Path(dirpath)
        for fname in filenames:
            fpath = p / fname
            if fname.endswith(".py"):
                all_py.add(fpath)
            elif fname.endswith((".jsx", ".tsx")):
                all_fe.add(fpath)

    # ── Python ────────────────────────────────────────────────────────────────
    for fpath in sorted(all_py):
        if fpath.name in _EXCLUDE_PY_NAMES:
            continue
        if _is_test_file(fpath):
            continue

        test_file = _find_test_for_python(fpath, all_py)
        matrix.entries.append(FileEntry(
            path=str(fpath.relative_to(root)),
            language="python",
            covered=bool(test_file),
            test_file=test_file,
        ))

    # ── React / Frontend ──────────────────────────────────────────────────────
    for fpath in sorted(all_fe):
        if _is_test_file(fpath):
            continue
        # Ignora arquivos de configuração comuns
        if fpath.name in {"main.jsx", "main.tsx", "vite.config.js"}:
            continue

        test_file = _find_test_for_jsx(fpath, all_fe)
        matrix.entries.append(FileEntry(
            path=str(fpath.relative_to(root)),
            language="react",
            covered=bool(test_file),
            test_file=test_file,
        ))

    return matrix
