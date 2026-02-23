"""
views.py  –  API JSON completa do AutoAuditor
----------------------------------------------
Todas as views retornam JSON puro.

Rotas (ver urls.py):
  GET   /autoauditor/api/status/              – health-check + ferramentas
  POST  /autoauditor/api/audit/django/        – bandit (salva SecurityAudit)
  POST  /autoauditor/api/audit/frontend/      – npm audit (salva SecurityAudit)
  POST  /autoauditor/api/generate/test/       – extrai AST, gera prompt IA
  POST  /autoauditor/api/run/tests/           – roda Pytest/Vitest/Playwright
  GET   /autoauditor/api/history/tests/       – histórico de TestRun
  GET   /autoauditor/api/history/security/    – histórico de SecurityAudit
  GET   /autoauditor/api/health/              – score atual + histórico
  POST  /autoauditor/api/health/              – força recálculo do score
  GET   /autoauditor/api/coverage/matrix/     – matriz de cobertura
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from .models import TestRun, SecurityAudit, ProjectHealth
from .utils.ast_parser import parse_file, skeleton_to_prompt, audit_django_cache_implementation
from .utils.cache_probe import CachePerformanceTester
from .utils.health import compute_health_score, build_coverage_matrix


# ── Utilitários internos ───────────────────────────────────────────────────────

def _json_body(request) -> dict:
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _project_root() -> Path:
    manage_py = Path(sys.argv[0]).resolve()
    if manage_py.name == "manage.py":
        return manage_py.parent
    return Path(os.getcwd()).resolve()


def _run_cmd(cmd: list, cwd=None, timeout: int = 180) -> tuple:
    """Executa subcomando e retorna (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=(sys.platform == "win32"),
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _refresh_health(project_root: Path) -> ProjectHealth:
    """Recalcula e salva um novo snapshot de ProjectHealth."""
    recent_runs = []
    for run_type in [TestRun.RunType.PYTEST, TestRun.RunType.VITEST, TestRun.RunType.PLAYWRIGHT]:
        run = TestRun.objects.filter(run_type=run_type).first()
        if run:
            recent_runs.append(run)

    recent_audits = []
    for tool in [SecurityAudit.Tool.BANDIT, SecurityAudit.Tool.NPM_AUDIT]:
        audit = SecurityAudit.objects.filter(tool=tool).first()
        if audit:
            recent_audits.append(audit)

    result = compute_health_score(recent_runs, recent_audits)
    matrix  = build_coverage_matrix(project_root)

    return ProjectHealth.objects.create(
        score=result.score,
        test_pass_rate=result.test_pass_rate,
        security_score=result.security_score,
        pytest_passed=result.pytest_passed,
        pytest_total=result.pytest_total,
        vitest_passed=result.vitest_passed,
        vitest_total=result.vitest_total,
        playwright_passed=result.playwright_passed,
        playwright_total=result.playwright_total,
        uncovered_files=[e.path for e in matrix.uncovered],
        covered_count=len(matrix.covered),
        uncovered_count=len(matrix.uncovered),
    )


def _health_to_dict(h: ProjectHealth) -> dict:
    return {
        "id": h.id, "created_at": h.created_at.isoformat(),
        "score": h.score, "grade": h.grade,
        "test_pass_rate": h.test_pass_rate, "security_score": h.security_score,
        "pytest_passed": h.pytest_passed, "pytest_total": h.pytest_total,
        "vitest_passed": h.vitest_passed, "vitest_total": h.vitest_total,
        "playwright_passed": h.playwright_passed, "playwright_total": h.playwright_total,
        "covered_count": h.covered_count, "uncovered_count": h.uncovered_count,
    }


def _testrun_to_dict(r: TestRun) -> dict:
    return {
        "id": r.id, "run_type": r.run_type,
        "created_at": r.created_at.isoformat(),
        "total": r.total, "passed": r.passed, "failed": r.failed,
        "errors": r.errors, "skipped": r.skipped,
        "pass_rate": r.pass_rate, "duration_seconds": r.duration_seconds,
        "exit_code": r.exit_code, "has_failures": r.has_failures,
    }


def _audit_to_dict(a: SecurityAudit) -> dict:
    return {
        "id": a.id, "tool": a.tool,
        "created_at": a.created_at.isoformat(),
        "info": a.info, "low": a.low, "medium": a.medium,
        "high": a.high, "critical": a.critical,
        "total_vulnerabilities": a.total_vulnerabilities,
        "security_score": a.security_score,
    }


def _parse_pytest_report(report: dict) -> dict:
    s = report.get("summary", {})
    return {
        "total": s.get("total", 0), "passed": s.get("passed", 0),
        "failed": s.get("failed", 0), "errors": s.get("error", 0),
        "skipped": s.get("skipped", 0), "duration": report.get("duration", 0.0),
    }


def _parse_vitest_report(report: dict) -> dict:
    return {
        "total": report.get("numTotalTests", 0),
        "passed": report.get("numPassedTests", 0),
        "failed": report.get("numFailedTests", 0),
        "errors": report.get("numFailedTestSuites", 0),
        "skipped": report.get("numPendingTests", 0),
        "duration": 0.0,
    }


def _parse_playwright_report(report: dict) -> dict:
    stats = report.get("stats", {})
    return {
        "total": stats.get("expected", 0) + stats.get("unexpected", 0) + stats.get("skipped", 0),
        "passed": stats.get("expected", 0),
        "failed": stats.get("unexpected", 0),
        "errors": 0,
        "skipped": stats.get("skipped", 0),
        "duration": stats.get("duration", 0.0) / 1000,
    }


# ── Views ──────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class StatusView(View):
    """GET /autoauditor/api/status/"""

    def get(self, request):
        def _check(cmd):
            try:
                return subprocess.run(
                    cmd, capture_output=True, shell=(sys.platform == "win32")
                ).returncode == 0
            except FileNotFoundError:
                return False

        return JsonResponse({
            "status": "ok",
            "autoauditor_version": "0.2.0",
            "tools": {
                "bandit":  _check(["bandit", "--version"]),
                "npm":     _check(["npm",    "--version"]),
                "pytest":  _check(["pytest", "--version"]),
                "npx":     _check(["npx",    "--version"]),
            },
            "project_root": str(_project_root()),
            "db_counts": {
                "test_runs":        TestRun.objects.count(),
                "security_audits":  SecurityAudit.objects.count(),
                "health_snapshots": ProjectHealth.objects.count(),
            },
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuditDjangoView(View):
    """
    POST /autoauditor/api/audit/django/
    Executa bandit, salva SecurityAudit no banco e atualiza o health score.
    """

    def post(self, request):
        body = _json_body(request)
        target_path = body.get("path") or str(_project_root())

        try:
            stdout, stderr, code = _run_cmd(
                ["bandit", "-f", "json", "-l", "-r", target_path], timeout=120
            )
        except FileNotFoundError:
            return JsonResponse({"success": False, "error": "bandit não encontrado. pip install bandit"}, status=500)
        except subprocess.TimeoutExpired:
            return JsonResponse({"success": False, "error": "Timeout: bandit > 120s"}, status=500)

        if not stdout:
            return JsonResponse({"success": False, "error": "bandit sem saída.", "stderr": stderr}, status=500)

        try:
            report = json.loads(stdout)
        except json.JSONDecodeError as e:
            return JsonResponse({"success": False, "error": f"JSON inválido: {e}"}, status=500)

        totals = report.get("metrics", {}).get("_totals", {})
        audit = SecurityAudit.objects.create(
            tool=SecurityAudit.Tool.BANDIT,
            low=int(totals.get("SEVERITY.LOW",    0)),
            medium=int(totals.get("SEVERITY.MEDIUM", 0)),
            high=int(totals.get("SEVERITY.HIGH",   0)),
            critical=0,
            raw_report=report,
            target_path=target_path,
        )
        _refresh_health(_project_root())

        return JsonResponse({
            "success": True, "tool": "bandit",
            "target": target_path, "saved_id": audit.id,
            "summary": _audit_to_dict(audit), "report": report,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuditFrontendView(View):
    """
    POST /autoauditor/api/audit/frontend/
    Executa npm audit, salva SecurityAudit no banco e atualiza o health score.
    """

    def post(self, request):
        body = _json_body(request)
        app_dir = Path(__file__).resolve().parent
        target_path = body.get("path") or str(app_dir / "frontend")

        if not Path(target_path).exists():
            return JsonResponse({"success": False, "error": f"Diretório não encontrado: {target_path}"}, status=400)
        if not (Path(target_path) / "package.json").exists():
            return JsonResponse({"success": False, "error": f"package.json não encontrado: {target_path}"}, status=400)

        try:
            stdout, stderr, code = _run_cmd(["npm", "audit", "--json"], cwd=target_path, timeout=120)
        except FileNotFoundError:
            return JsonResponse({"success": False, "error": "npm não encontrado."}, status=500)
        except subprocess.TimeoutExpired:
            return JsonResponse({"success": False, "error": "Timeout: npm audit > 120s"}, status=500)

        if not stdout:
            return JsonResponse({"success": False, "error": "npm audit sem saída.", "stderr": stderr}, status=500)

        try:
            report = json.loads(stdout)
        except json.JSONDecodeError as e:
            return JsonResponse({"success": False, "error": f"JSON inválido: {e}"}, status=500)

        vuln = report.get("metadata", {}).get("vulnerabilities", {})
        audit = SecurityAudit.objects.create(
            tool=SecurityAudit.Tool.NPM_AUDIT,
            info=int(vuln.get("info",     0)),
            low=int(vuln.get("low",       0)),
            medium=int(vuln.get("moderate", vuln.get("medium", 0))),
            high=int(vuln.get("high",     0)),
            critical=int(vuln.get("critical", 0)),
            raw_report=report,
            target_path=target_path,
        )
        _refresh_health(_project_root())

        return JsonResponse({
            "success": True, "tool": "npm audit",
            "target": target_path, "saved_id": audit.id,
            "summary": _audit_to_dict(audit), "report": report,
        })


@method_decorator(csrf_exempt, name="dispatch")
class GenerateTestView(View):
    """
    POST /autoauditor/api/generate/test/

    Body JSON:
        {
            "file_path": "/caminho/absoluto/para/models.py",
            "framework": "django" | "generic"    // default: "django"
        }

    1. Usa ast_parser para extrair o esqueleto do arquivo .py
    2. Monta um prompt enxuto (sem enviar o arquivo inteiro)
    3. Retorna o prompt pronto para ser enviado a uma IA (GPT, Gemini, etc.)

    O frontend React pode copiar este prompt ou enviá-lo diretamente para
    a API de IA que o desenvolvedor configurar.
    """

    def post(self, request):
        body = _json_body(request)
        file_path = body.get("file_path", "").strip()
        framework = body.get("framework", "django")

        if not file_path:
            return JsonResponse({
                "success": False,
                "error": "Campo `file_path` é obrigatório.",
            }, status=400)

        if not file_path.endswith(".py"):
            return JsonResponse({
                "success": False,
                "error": "Apenas arquivos .py são suportados.",
            }, status=400)

        target = Path(file_path)
        if not target.exists():
            return JsonResponse({
                "success": False,
                "error": f"Arquivo não encontrado: {file_path}",
            }, status=404)

        try:
            skeleton = parse_file(target)
            prompt = skeleton_to_prompt(skeleton, framework=framework)

            return JsonResponse({
                "success": True,
                "file": str(target),
                "summary": {
                    "classes": len(skeleton.classes),
                    "top_level_functions": len(skeleton.top_level_functions),
                    "imports": len(skeleton.imports),
                    "class_names": [cls.name for cls in skeleton.classes],
                },
                "prompt": prompt,
            })

        except SyntaxError as exc:
            return JsonResponse({"success": False, "error": f"Erro de sintaxe: {exc}"}, status=422)
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# RunTestsView  –  Pytest / Vitest / Playwright
# ══════════════════════════════════════════════════════════════════════════════

@method_decorator(csrf_exempt, name="dispatch")
class RunTestsView(View):
    """
    POST /autoauditor/api/run/tests/
    Body: { "tool": "pytest|vitest|playwright", "path": "..." }
    Executa a suite, salva TestRun e recalcula o ProjectHealth.
    """

    def post(self, request):
        body = _json_body(request)
        tool = body.get("tool", "").strip().lower()
        if tool not in ("pytest", "vitest", "playwright"):
            return JsonResponse(
                {"success": False, "error": "tool deve ser: pytest | vitest | playwright"}, status=400
            )
        target_path = body.get("path") or str(_project_root())
        specific    = body.get("specific", "").strip()
        try:
            if tool == "pytest":
                return self._run_pytest(target_path, specific)
            elif tool == "vitest":
                return self._run_vitest(target_path, specific)
            return self._run_playwright(target_path, specific)
        except subprocess.TimeoutExpired:
            return JsonResponse({"success": False, "error": f"Timeout: {tool} > 180s"}, status=500)
        except FileNotFoundError as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=500)

    def _save_run(self, run_type: str, stats: dict, report: dict, target: str, code: int, stderr: str) -> TestRun:
        run = TestRun.objects.create(
            run_type=run_type,
            total=stats["total"], passed=stats["passed"],
            failed=stats["failed"], errors=stats["errors"],
            skipped=stats["skipped"], duration_seconds=stats["duration"],
            raw_report=report, target_path=target,
            exit_code=code, stderr_output=stderr[:4000],
        )
        _refresh_health(_project_root())
        return run

    def _run_pytest(self, target_path: str, specific: str = "") -> JsonResponse:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        test_target = specific if specific else target_path
        cmd = ["pytest", "--json-report", f"--json-report-file={report_file}", "--tb=short", "-q", test_target]
        try:
            stdout, stderr, code = _run_cmd(cmd, timeout=180)
        except FileNotFoundError:
            raise FileNotFoundError("pytest não encontrado. pip install pytest pytest-json-report")

        rp = Path(report_file)
        if not rp.exists() or rp.stat().st_size == 0:
            return JsonResponse({
                "success": False,
                "error": "pytest não gerou JSON. pip install pytest-json-report",
                "stdout": stdout, "stderr": stderr,
            }, status=500)
        report = json.loads(rp.read_text(encoding="utf-8"))
        try:
            rp.unlink()
        except OSError:
            pass
        run = self._save_run(TestRun.RunType.PYTEST, _parse_pytest_report(report), report, test_target, code, stderr)
        return JsonResponse({
            "success": True, "tool": "pytest", "saved_id": run.id,
            "summary": _testrun_to_dict(run),
            "stdout": stdout, "stderr": stderr,
        })

    def _run_vitest(self, target_path: str, specific: str = "") -> JsonResponse:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        cmd = ["npx", "vitest", "run", "--reporter=json", f"--outputFile={report_file}"]
        if specific:
            cmd.append(specific)
        try:
            stdout, stderr, code = _run_cmd(cmd, cwd=target_path, timeout=180)
        except FileNotFoundError:
            raise FileNotFoundError("npx não encontrado. Instale o Node.js.")

        rp = Path(report_file)
        report: dict = {}
        if rp.exists() and rp.stat().st_size > 0:
            try:
                report = json.loads(rp.read_text(encoding="utf-8"))
            finally:
                try: rp.unlink()
                except OSError: pass
        elif stdout:
            try:
                report = json.loads(stdout)
            except json.JSONDecodeError:
                return JsonResponse({"success": False, "error": "vitest saída inválida.", "stderr": stderr}, status=500)

        if not report:
            return JsonResponse({"success": False, "error": "vitest não gerou relatório.", "stderr": stderr}, status=500)

        run = self._save_run(TestRun.RunType.VITEST, _parse_vitest_report(report), report, target_path, code, stderr)
        return JsonResponse({
            "success": True, "tool": "vitest", "saved_id": run.id,
            "summary": _testrun_to_dict(run),
            "stdout": stdout, "stderr": stderr,
        })

    def _run_playwright(self, target_path: str, specific: str = "") -> JsonResponse:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        cmd = ["npx", "playwright", "test", "--reporter=json"]
        if specific:
            cmd.append(specific)
        env = os.environ.copy()
        env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = report_file
        try:
            result = subprocess.run(
                cmd, cwd=target_path, capture_output=True, text=True,
                timeout=300, shell=(sys.platform == "win32"), env=env,
            )
            stdout, stderr, code = result.stdout.strip(), result.stderr.strip(), result.returncode
        except FileNotFoundError:
            raise FileNotFoundError("npx não encontrado. Instale o Node.js.")

        rp = Path(report_file)
        report: dict = {}
        if rp.exists() and rp.stat().st_size > 0:
            try:
                report = json.loads(rp.read_text(encoding="utf-8"))
            finally:
                try: rp.unlink()
                except OSError: pass
        if not report and stdout:
            try: report = json.loads(stdout)
            except json.JSONDecodeError: pass
        if not report:
            return JsonResponse({"success": False, "error": "Playwright sem relatório. npx playwright install", "stderr": stderr[:2000]}, status=500)

        run = self._save_run(TestRun.RunType.PLAYWRIGHT, _parse_playwright_report(report), report, target_path, code, stderr)
        return JsonResponse({
            "success": True, "tool": "playwright", "saved_id": run.id,
            "summary": _testrun_to_dict(run),
            "stdout": stdout, "stderr": stderr,
        })


# ══════════════════════════════════════════════════════════════════════════════
# RunTestsStreamView  –  SSE streaming em tempo real
# ══════════════════════════════════════════════════════════════════════════════

@method_decorator(csrf_exempt, name="dispatch")
class RunTestsStreamView(RunTestsView):
    """
    POST /autoauditor/api/run/stream/
    Executa pytest/vitest/playwright e faz stream do output linha a linha via SSE.

    Eventos emitidos:
      { "type": "line",   "text": "..."  }           -- linha de saida
      { "type": "result", "success": true, ... }     -- resultado final (salvo no banco)
      { "type": "error",  "message": "..." }         -- erro fatal
    """

    def post(self, request):
        body        = _json_body(request)
        tool        = body.get("tool", "pytest").strip().lower()
        target_path = body.get("path") or str(_project_root())
        specific    = body.get("specific", "").strip()

        if tool not in ("pytest", "vitest", "playwright"):
            def _err():
                yield self._sse({"type": "error", "message": "tool deve ser: pytest | vitest | playwright"})
            resp = StreamingHttpResponse(_err(), content_type="text/event-stream")
            self._sse_headers(resp)
            return resp

        gen = {
            "pytest":     self._stream_pytest,
            "vitest":     self._stream_vitest,
            "playwright": self._stream_playwright,
        }[tool](target_path, specific)

        resp = StreamingHttpResponse(gen, content_type="text/event-stream")
        self._sse_headers(resp)
        return resp

    @staticmethod
    def _sse_headers(response):
        response["Cache-Control"]               = "no-cache"
        response["X-Accel-Buffering"]           = "no"
        response["Access-Control-Allow-Origin"] = "*"

    def _sse(self, data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _popen(self, cmd, cwd=None, env=None):
        e = (env or os.environ).copy()
        e["PYTHONUNBUFFERED"] = "1"
        return subprocess.Popen(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            shell=(sys.platform == "win32"), env=e, bufsize=1,
        )

    def _stream_pytest(self, target_path: str, specific: str):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        test_target = specific if specific else target_path
        pytest_exe  = str(Path(sys.executable).parent / "pytest")
        cmd = [pytest_exe, "--json-report", f"--json-report-file={report_file}",
               "--tb=short", "-v", "--no-header", test_target]
        try:
            proc = self._popen(cmd)
        except FileNotFoundError:
            yield self._sse({"type": "error", "message": "pytest não encontrado."})
            return

        for raw in proc.stdout:
            yield self._sse({"type": "line", "text": raw.rstrip("\r\n")})
        proc.wait()

        rp = Path(report_file)
        if not rp.exists() or rp.stat().st_size == 0:
            yield self._sse({"type": "error", "message": "pytest não gerou JSON. pip install pytest-json-report"})
            return
        try:
            report = json.loads(rp.read_text(encoding="utf-8"))
            rp.unlink()
        except Exception as exc:
            yield self._sse({"type": "error", "message": f"Erro ao ler relatório: {exc}"})
            return

        run = self._save_run(
            TestRun.RunType.PYTEST, _parse_pytest_report(report),
            report, test_target, proc.returncode, "",
        )
        failures = [
            {"nodeid": t["nodeid"], "longrepr": (t.get("call") or {}).get("longrepr", "")}
            for t in report.get("tests", [])
            if t.get("outcome") == "failed"
        ]
        yield self._sse({
            "type": "result", "success": True, "tool": "pytest",
            "saved_id": run.id, "summary": _testrun_to_dict(run), "failures": failures,
        })

    def _stream_vitest(self, target_path: str, specific: str):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        cmd = ["npx", "vitest", "run", "--reporter=verbose",
               "--reporter=json", f"--outputFile={report_file}"]
        if specific:
            cmd.append(specific)
        try:
            proc = self._popen(cmd, cwd=target_path)
        except FileNotFoundError:
            yield self._sse({"type": "error", "message": "npx não encontrado."})
            return

        for raw in proc.stdout:
            yield self._sse({"type": "line", "text": raw.rstrip("\r\n")})
        proc.wait()

        rp = Path(report_file)
        report = {}
        if rp.exists() and rp.stat().st_size > 0:
            try:
                report = json.loads(rp.read_text(encoding="utf-8"))
                rp.unlink()
            except Exception:
                pass
        if not report:
            yield self._sse({"type": "error", "message": "vitest não gerou relatório."})
            return

        run = self._save_run(
            TestRun.RunType.VITEST, _parse_vitest_report(report),
            report, target_path, proc.returncode, "",
        )
        failures = [
            {"nodeid": a["fullName"], "longrepr": "\n".join(a.get("failureMessages", []))}
            for suite in report.get("testResults", [])
            for a in suite.get("assertionResults", [])
            if a.get("status") == "failed"
        ]
        yield self._sse({
            "type": "result", "success": True, "tool": "vitest",
            "saved_id": run.id, "summary": _testrun_to_dict(run), "failures": failures,
        })

    def _stream_playwright(self, target_path: str, specific: str):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            report_file = tmp.name
        cmd = ["npx", "playwright", "test", "--reporter=list,json"]
        if specific:
            cmd.append(specific)
        env = os.environ.copy()
        env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = report_file
        try:
            proc = self._popen(cmd, cwd=target_path, env=env)
        except FileNotFoundError:
            yield self._sse({"type": "error", "message": "npx não encontrado."})
            return

        for raw in proc.stdout:
            yield self._sse({"type": "line", "text": raw.rstrip("\r\n")})
        proc.wait()

        rp = Path(report_file)
        report = {}
        if rp.exists() and rp.stat().st_size > 0:
            try:
                report = json.loads(rp.read_text(encoding="utf-8"))
                rp.unlink()
            except Exception:
                pass
        if not report:
            yield self._sse({"type": "error", "message": "Playwright sem relatório."})
            return

        run = self._save_run(
            TestRun.RunType.PLAYWRIGHT, _parse_playwright_report(report),
            report, target_path, proc.returncode, "",
        )

        def _extract_pw_failures(suites):
            for suite in (suites or []):
                for spec in suite.get("specs", []):
                    for test in spec.get("tests", []):
                        for result in test.get("results", []):
                            if result.get("status") == "failed":
                                yield {
                                    "nodeid":   spec.get("title", ""),
                                    "longrepr": (result.get("error") or {}).get("message", ""),
                                }
                for child in suite.get("suites", []):
                    yield from _extract_pw_failures([child])

        failures = list(_extract_pw_failures(report.get("suites", [])))
        yield self._sse({
            "type": "result", "success": True, "tool": "playwright",
            "saved_id": run.id, "summary": _testrun_to_dict(run), "failures": failures,
        })


# ── Histórico ─────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class TestHistoryView(View):
    """GET /autoauditor/api/history/tests/?tool=pytest&limit=50"""

    def get(self, request):
        tool  = request.GET.get("tool")
        limit = min(int(request.GET.get("limit", 50)), 200)
        qs = TestRun.objects.all()
        if tool in ("pytest", "vitest", "playwright"):
            qs = qs.filter(run_type=tool)
        runs = list(qs[:limit])
        return JsonResponse({"success": True, "count": len(runs), "results": [_testrun_to_dict(r) for r in runs]})


@method_decorator(csrf_exempt, name="dispatch")
class SecurityHistoryView(View):
    """GET /autoauditor/api/history/security/?tool=bandit&limit=50"""

    def get(self, request):
        tool  = request.GET.get("tool")
        limit = min(int(request.GET.get("limit", 50)), 200)
        qs = SecurityAudit.objects.all()
        if tool in ("bandit", "npm_audit"):
            qs = qs.filter(tool=tool)
        audits = list(qs[:limit])
        return JsonResponse({"success": True, "count": len(audits), "results": [_audit_to_dict(a) for a in audits]})


# ── Health Score ──────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class ProjectHealthView(View):
    """
    GET  /autoauditor/api/health/?limit=30  → snapshot atual + histórico
    POST /autoauditor/api/health/           → força recálculo agora
    """

    def get(self, request):
        limit   = min(int(request.GET.get("limit", 30)), 120)
        latest  = ProjectHealth.objects.first()
        history = list(ProjectHealth.objects.all()[:limit])
        return JsonResponse({
            "success": True,
            "latest":  _health_to_dict(latest) if latest else None,
            "history": [_health_to_dict(h) for h in reversed(history)],
        })

    def post(self, request):
        snapshot = _refresh_health(_project_root())
        return JsonResponse({"success": True, "message": "Health score recalculado.", "snapshot": _health_to_dict(snapshot)})


# ── Cache Audit ──────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class CacheAuditView(View):
    """
    GET  /autoauditor/api/audit/cache/?path=<views.py>
         Analisa estaticamente um arquivo de views/viewsets e retorna a
         matriz de cobertura de cache: quais ViewSets têm o mixin, quais
         ações de escrita invalidam o cache e quais estão em falta.

    POST /autoauditor/api/audit/cache/
         Executa um probe dinâmico de 4 passos (MISS → HIT → mutação → MISS)
         contra um endpoint real.

         Body JSON:
         {
             "url":              "http://localhost:8000/api/ferias-solicitacoes/",
             "token":            "<Bearer token>",
             "mutation_payload": { ... },          // optional
             "mutation_method":  "POST",            // default "POST"
             "mutation_url":     null,              // optional; usa url se null
             "extra_headers":    {                  // optional
                 "X-Active-Profile-Code": "COORDENADOR"
             },
             "timeout_s":        10                 // optional
         }
    """

    # ── GET: auditoria estática via AST ──────────────────────────────────────

    def get(self, request):
        path_param = request.GET.get("path", "").strip()

        if path_param:
            # Audita um único arquivo informado
            target = Path(path_param)
            if not target.exists():
                return JsonResponse(
                    {"success": False, "error": f"Arquivo não encontrado: {path_param}"},
                    status=400,
                )
            try:
                result = audit_django_cache_implementation(target)
            except SyntaxError as exc:
                return JsonResponse({"success": False, "error": f"Erro de sintaxe: {exc}"}, status=422)
            except Exception as exc:
                return JsonResponse({"success": False, "error": str(exc)}, status=500)
            return JsonResponse({"success": True, "results": [result]})

        # Sem path: varre arquivos views.py do project_root automaticamente
        project_root = _project_root()
        views_files = list(project_root.rglob("views.py"))

        # Filtra paths irrelevantes (migrações, node_modules, venv, __pycache__)
        _SKIP = {".venv", "venv", "node_modules", "__pycache__", "migrations", ".git"}
        views_files = [
            f for f in views_files
            if not any(part in _SKIP for part in f.parts)
        ]

        all_results: list[dict] = []
        errors: list[dict] = []

        for vf in views_files:
            try:
                r = audit_django_cache_implementation(vf)
                if r["viewsets_found"] > 0:
                    # Torna o caminho relativo para legibilidade
                    rel = str(vf.relative_to(project_root))
                    r["file"] = rel
                    all_results.append(r)
            except SyntaxError as exc:
                errors.append({"file": str(vf), "error": f"SyntaxError: {exc}"})
            except Exception as exc:
                errors.append({"file": str(vf), "error": str(exc)})

        # Monta sumário agregado
        total_viewsets = sum(r["viewsets_found"] for r in all_results)
        total_with_mixin = sum(
            sum(1 for v in r["viewsets"] if v["cache_mixin_present"])
            for r in all_results
        )
        total_with_issues = sum(
            sum(1 for v in r["viewsets"] if v["issues"])
            for r in all_results
        )
        overall = (
            "healthy" if total_with_issues == 0
            else "warning" if total_with_mixin > 0
            else "critical"
        )

        return JsonResponse({
            "success": True,
            "project_root": str(project_root),
            "files_scanned": len(views_files),
            "files_with_viewsets": len(all_results),
            "summary": {
                "total_viewsets": total_viewsets,
                "viewsets_with_cache_mixin": total_with_mixin,
                "viewsets_with_issues": total_with_issues,
                "overall_status": overall,
            },
            "results": all_results,
            "errors": errors,
        })

    # ── POST: probe dinâmico de cache ────────────────────────────────────────

    def post(self, request):
        body = _json_body(request)
        url = body.get("url", "").strip()
        token = body.get("token", "").strip()

        if not url:
            return JsonResponse(
                {"success": False, "error": "Campo 'url' é obrigatório."},
                status=400,
            )
        if not token:
            return JsonResponse(
                {"success": False, "error": "Campo 'token' é obrigatório."},
                status=400,
            )

        tester = CachePerformanceTester(
            url=url,
            token=token,
            mutation_payload=body.get("mutation_payload") or {},
            mutation_method=body.get("mutation_method", "POST"),
            mutation_url=body.get("mutation_url") or None,
            extra_headers=body.get("extra_headers") or {},
            timeout_s=float(body.get("timeout_s", 10)),
        )

        try:
            report = tester.run()
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=500)

        return JsonResponse({
            "success": True,
            "report": report.to_dict(),
        })


# ── Coverage Matrix ───────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class CoverageMatrixView(View):
    """GET /autoauditor/api/coverage/matrix/?path=<project_root>"""

    def get(self, request):
        path = request.GET.get("path") or str(_project_root())
        if not Path(path).exists():
            return JsonResponse({"success": False, "error": f"Caminho não encontrado: {path}"}, status=400)
        matrix = build_coverage_matrix(path)
        return JsonResponse({
            "success": True, "project_root": path,
            "coverage_pct": matrix.coverage_pct,
            "total": len(matrix.entries),
            "covered_count": len(matrix.covered),
            "uncovered_count": len(matrix.uncovered),
            "uncovered": [{"path": e.path, "language": e.language} for e in matrix.uncovered],
            "covered":   [{"path": e.path, "language": e.language, "test_file": e.test_file} for e in matrix.covered],
        })
