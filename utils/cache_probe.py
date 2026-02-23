"""
cache_probe.py  –  Motor de Probes Dinâmicos de Cache
------------------------------------------------------
Valida o ciclo de vida do cache HTTP em endpoints Django/DRF que retornam
o header ``X-API-Cache`` (HIT | MISS | BYPASS).

Fluxo de probe padrão (4 passos):
  1. GET  → espera MISS (cache frio)
  2. GET  → espera HIT  (cache aquecido); mede redução de latência
  3. POST | PATCH (mutação com payload fornecido)
  4. GET  → espera MISS (invalidação confirmada)

Sem dependências externas: usa ``urllib`` da stdlib.
Se ``requests`` estiver disponível, é usado automaticamente (mais ergonômico).
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# ── header canônico que o sistema usa ─────────────────────────────────────────
_CACHE_HEADER = "x-api-cache"
_HIT = "HIT"
_MISS = "MISS"
_BYPASS = "BYPASS"

# Tenta usar `requests` se disponível
try:
    import requests as _requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ── Tipos de resultado ─────────────────────────────────────────────────────────

@dataclass
class ProbeStep:
    step: int
    method: str                     # GET | POST | PATCH | PUT | DELETE
    url: str
    status_code: int
    cache_status: str               # HIT | MISS | BYPASS | NONE
    latency_ms: float
    expected_cache: str | None = None
    passed: bool = True
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "method": self.method,
            "url": self.url,
            "status_code": self.status_code,
            "cache_status": self.cache_status,
            "expected_cache": self.expected_cache,
            "latency_ms": round(self.latency_ms, 2),
            "passed": self.passed,
            "note": self.note,
        }


@dataclass
class CacheProbeReport:
    endpoint: str
    mutation_method: str
    steps: list[ProbeStep] = field(default_factory=list)
    warmup_ok: bool = False          # GET 1→2 retornou HIT
    invalidation_ok: bool = False    # GET pós-mutação retornou MISS
    speedup_ratio: float = 0.0       # latência_cold / latência_warm
    get_latencies_ms: list[float] = field(default_factory=list)
    error: str | None = None

    # ── propriedades de latência aproximada ───────────────────────────────────

    @property
    def p50_ms(self) -> float:
        if not self.get_latencies_ms:
            return 0.0
        return round(statistics.median(self.get_latencies_ms), 2)

    @property
    def p95_ms(self) -> float:
        if not self.get_latencies_ms:
            return 0.0
        s = sorted(self.get_latencies_ms)
        idx = max(0, int(len(s) * 0.95) - 1)
        return round(s[idx], 2)

    @property
    def overall_passed(self) -> bool:
        if self.error:
            return False
        return all(s.passed for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "mutation_method": self.mutation_method,
            "overall_passed": self.overall_passed,
            "warmup_ok": self.warmup_ok,
            "invalidation_ok": self.invalidation_ok,
            "speedup_ratio": round(self.speedup_ratio, 2),
            "latency_p50_ms": self.p50_ms,
            "latency_p95_ms": self.p95_ms,
            "error": self.error,
            "steps": [s.to_dict() for s in self.steps],
        }


# ── HTTP helpers (urllib + requests como opt-in) ───────────────────────────────

def _do_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, str], Any]:
    """
    Executa uma requisição HTTP e retorna (status_code, response_headers, body_json_or_none).

    Usa `requests` se disponível, caso contrário `urllib`.
    """
    if _HAS_REQUESTS:
        return _do_request_requests(method, url, headers, body, timeout)
    return _do_request_urllib(method, url, headers, body, timeout)


def _do_request_requests(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict | None,
    timeout: float,
) -> tuple[int, dict[str, str], Any]:
    resp = _requests.request(
        method=method,
        url=url,
        headers=headers,
        json=body,
        timeout=timeout,
    )
    resp_headers = {k.lower(): v for k, v in resp.headers.items()}
    try:
        body_json = resp.json()
    except Exception:
        body_json = None
    return resp.status_code, resp_headers, body_json


def _do_request_urllib(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict | None,
    timeout: float,
) -> tuple[int, dict[str, str], Any]:
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            try:
                body_json = json.loads(raw)
            except Exception:
                body_json = None
            return resp.status, resp_headers, body_json
    except urllib.error.HTTPError as exc:
        resp_headers = {k.lower(): v for k, v in exc.headers.items()}
        return exc.code, resp_headers, None


# ── Classe principal ──────────────────────────────────────────────────────────

class CachePerformanceTester:
    """
    Executa um probe de 4 passos para validar o ciclo de vida do cache de um
    endpoint DRF que emite o header ``X-API-Cache``.

    Args:
        url:              URL do endpoint de listagem (ex: ``http://localhost:8000/api/ferias-solicitacoes/``).
        token:            Token de autorização (será enviado como ``Authorization: Bearer <token>``).
        mutation_payload: Payload JSON para o passo de mutação (POST/PATCH).
        mutation_method:  Verbo HTTP da mutação (default ``"POST"``).
        mutation_url:     URL alternativa para a mutação. Se None, usa a mesma ``url``.
        extra_headers:    Headers adicionais (ex: ``{"X-Active-Profile-Code": "COORDENADOR"}``).
        timeout_s:        Timeout por requisição em segundos (default ``10``).

    Exemplo::

        tester = CachePerformanceTester(
            url="http://localhost:8000/api/ferias-solicitacoes/",
            token="abc123",
            mutation_payload={"servidor": 1, "data_inicio": "2026-01-10", ...},
            extra_headers={"X-Active-Profile-Code": "COORDENADOR"},
        )
        report = tester.run()
        print(report.to_dict())
    """

    def __init__(
        self,
        url: str,
        token: str,
        mutation_payload: dict | None = None,
        mutation_method: str = "POST",
        mutation_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self.url = url.rstrip("/") + "/"
        self.mutation_url = (mutation_url or url).rstrip("/") + "/"
        self.token = token
        self.mutation_payload = mutation_payload or {}
        self.mutation_method = mutation_method.upper()
        self.timeout_s = timeout_s
        self._base_headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if extra_headers:
            self._base_headers.update(extra_headers)

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _get(self, step_num: int, expected: str | None = None) -> ProbeStep:
        t0 = time.perf_counter()
        try:
            status, resp_headers, _ = _do_request(
                "GET", self.url, self._base_headers, timeout=self.timeout_s
            )
        except Exception as exc:
            return ProbeStep(
                step=step_num, method="GET", url=self.url,
                status_code=0, cache_status="NONE",
                latency_ms=0.0, expected_cache=expected,
                passed=False, note=f"Erro de conexão: {exc}",
            )
        latency_ms = (time.perf_counter() - t0) * 1000
        cache_status = resp_headers.get(_CACHE_HEADER, "NONE").upper()
        passed = (expected is None) or (cache_status == expected)
        note = "" if passed else f"Esperado {expected}, recebido {cache_status}"
        return ProbeStep(
            step=step_num, method="GET", url=self.url,
            status_code=status, cache_status=cache_status,
            latency_ms=latency_ms, expected_cache=expected,
            passed=passed, note=note,
        )

    def _mutate(self, step_num: int) -> ProbeStep:
        t0 = time.perf_counter()
        try:
            status, _, _ = _do_request(
                self.mutation_method, self.mutation_url,
                self._base_headers, body=self.mutation_payload,
                timeout=self.timeout_s,
            )
        except Exception as exc:
            return ProbeStep(
                step=step_num, method=self.mutation_method,
                url=self.mutation_url, status_code=0,
                cache_status="NONE", latency_ms=0.0,
                passed=False, note=f"Erro de conexão: {exc}",
            )
        latency_ms = (time.perf_counter() - t0) * 1000
        passed = status < 400
        note = "" if passed else f"Mutação falhou com HTTP {status}"
        return ProbeStep(
            step=step_num, method=self.mutation_method,
            url=self.mutation_url, status_code=status,
            cache_status="NONE", latency_ms=latency_ms,
            passed=passed, note=note,
        )

    # ── Probe principal ───────────────────────────────────────────────────────

    def run(self) -> CacheProbeReport:
        """
        Executa os 4 passos do probe e retorna um :class:`CacheProbeReport`.

        Passos:
            1. GET → MISS  (cache frio)
            2. GET → HIT   (cache aquecido)
            3. Mutação (POST/PATCH/...)
            4. GET → MISS  (invalidação confirmada)
        """
        report = CacheProbeReport(
            endpoint=self.url,
            mutation_method=self.mutation_method,
        )

        try:
            # ── Passo 1: cache frio ────────────────────────────────────────
            step1 = self._get(step_num=1, expected=_MISS)
            report.steps.append(step1)

            if not step1.passed and step1.status_code == 0:
                report.error = step1.note
                return report

            # ── Passo 2: cache aquecido ────────────────────────────────────
            step2 = self._get(step_num=2, expected=_HIT)
            report.steps.append(step2)
            report.warmup_ok = step2.passed

            # Coleta latências dos GETs para p50/p95
            report.get_latencies_ms.extend([step1.latency_ms, step2.latency_ms])

            if step1.latency_ms > 0 and step2.latency_ms > 0:
                report.speedup_ratio = round(step1.latency_ms / step2.latency_ms, 2)

            # ── Passo 3: mutação (invalidação) ────────────────────────────
            step3 = self._mutate(step_num=3)
            report.steps.append(step3)

            # ── Passo 4: confirma invalidação ──────────────────────────────
            step4 = self._get(step_num=4, expected=_MISS)
            report.steps.append(step4)
            report.get_latencies_ms.append(step4.latency_ms)
            report.invalidation_ok = step4.passed

        except Exception as exc:
            report.error = str(exc)

        return report

    # ── Probe estendido (múltiplos GETs para latência mais precisa) ──────────

    def run_latency_warmup(self, n_warm: int = 10) -> CacheProbeReport:
        """
        Variante que faz ``n_warm`` GETs adicionais para calcular latências
        p50/p95 mais representativas do cenário de cache quente.

        Não executa a mutação. Útil apenas para profiling de latência.
        """
        report = CacheProbeReport(
            endpoint=self.url,
            mutation_method="N/A",
        )
        # GET inicial (cache frio)
        step = self._get(step_num=1, expected=_MISS)
        report.steps.append(step)
        report.get_latencies_ms.append(step.latency_ms)

        if step.status_code == 0:
            report.error = step.note
            return report

        # GETs para aquecer e medir
        for i in range(n_warm):
            s = self._get(step_num=i + 2, expected=_HIT)
            report.steps.append(s)
            report.get_latencies_ms.append(s.latency_ms)

        report.warmup_ok = all(s.cache_status == _HIT for s in report.steps[1:])
        if report.get_latencies_ms:
            cold = report.get_latencies_ms[0]
            warm_latencies = report.get_latencies_ms[1:]
            if warm_latencies:
                avg_warm = statistics.mean(warm_latencies)
                report.speedup_ratio = round(cold / avg_warm, 2) if avg_warm > 0 else 0.0
        return report
