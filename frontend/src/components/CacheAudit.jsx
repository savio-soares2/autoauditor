import { useState } from "react";
import axios from "axios";

// ── helpers de badge ────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    healthy:  "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    warning:  "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    critical: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  return (
    <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wide border ${map[status] ?? "bg-slate-700 text-slate-400 border-slate-600"}`}>
      {status ?? "–"}
    </span>
  );
}

function CacheStatusBadge({ value }) {
  const map = {
    HIT:    "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    MISS:   "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    BYPASS: "bg-slate-700/50 text-slate-400 border-slate-600",
    NONE:   "bg-slate-800 text-slate-600 border-slate-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold border ${map[value] ?? "bg-slate-700 text-slate-400 border-slate-600"}`}>
      {value ?? "–"}
    </span>
  );
}

function PassBadge({ passed }) {
  return passed
    ? <span className="text-emerald-400 font-bold">✓ ok</span>
    : <span className="text-red-400 font-bold">✗ falhou</span>;
}

// ── Seção 1: Auditoria Estática ─────────────────────────────────────────────

function StaticAudit() {
  const [filePath, setFilePath] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [data,     setData]     = useState(null);
  const [error,    setError]    = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const params = filePath.trim() ? { path: filePath.trim() } : {};
      const { data: res } = await axios.get("/autoauditor/api/audit/cache/", { params });
      setData(res);
    } catch (e) {
      setError(e.response?.data?.error ?? e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Controles */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="flex-1 min-w-64">
          <label className="block text-sm font-semibold text-slate-300 mb-1.5">
            Arquivo específico <span className="text-slate-500 font-normal">(deixe vazio para varrer o projeto todo)</span>
          </label>
          <input
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="ex: C:\...\backend\core\views.py"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all"
          />
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
          style={{boxShadow:'0 0 16px rgba(99,102,241,0.25)'}}
        >
          {loading ? "Analisando…" : "Analisar"}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm font-medium text-red-400">{error}</div>
      )}

      {data && (
        <div className="space-y-6">
          {/* Sumário */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Arquivos varridos",      value: data.files_scanned ?? 1 },
              { label: "ViewSets encontrados",   value: data.summary?.total_viewsets ?? data.viewsets_found },
              { label: "Com mixin de cache",     value: data.summary?.viewsets_with_cache_mixin ?? "–" },
              { label: "Com pendências",         value: data.summary?.viewsets_with_issues ?? data.results?.flatMap(r => r.viewsets).filter(v => v.issues?.length).length ?? 0 },
            ].map((c) => (
              <div key={c.label} className="bg-slate-900 border border-slate-700/50 rounded-xl p-4 text-center">
                <div className="text-3xl font-extrabold text-slate-100">{c.value}</div>
                <div className="text-xs font-semibold text-slate-500 mt-1 uppercase tracking-wide">{c.label}</div>
              </div>
            ))}
          </div>

          {/* Status geral */}
          <div className="flex items-center gap-3 text-sm font-medium text-slate-400 bg-slate-800/50 p-3 rounded-lg border border-slate-700/50 inline-flex">
            <span>Status geral:</span>
            <StatusBadge status={data.summary?.overall_status ?? data.overall_status} />
          </div>

          {/* Matriz de ViewSets */}
          {(data.results ?? [data]).map((fileResult) => (
            <div key={fileResult.file} className="bg-slate-900 border border-slate-700/50 rounded-xl overflow-hidden">
              <div className="px-5 py-3 bg-slate-800/50 border-b border-slate-700/50 text-sm text-slate-400 font-mono font-semibold truncate">
                {fileResult.file}
              </div>
              {fileResult.viewsets.length === 0 ? (
                <p className="p-5 text-sm text-slate-500 font-medium">Nenhum ViewSet encontrado.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-700/50 bg-slate-900">
                        <th className="px-5 py-3">ViewSet</th>
                        <th className="text-center px-4 py-3">Mixin</th>
                        <th className="px-5 py-3">Métodos de escrita</th>
                        <th className="text-center px-4 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {fileResult.viewsets.map((vs) => (
                        <tr key={vs.name} className="hover:bg-slate-800/40 transition-colors">
                          <td className="px-5 py-3 font-mono font-medium text-slate-200">{vs.name}</td>
                          <td className="px-4 py-3 text-center">
                            {vs.cache_mixin_present
                              ? <span className="text-emerald-400 font-bold text-lg">✓</span>
                              : <span className="text-red-400 font-bold text-lg">✗</span>}
                          </td>
                          <td className="px-5 py-3">
                            {vs.write_methods.length === 0
                              ? <span className="text-slate-600 text-xs font-medium italic">nenhum</span>
                              : (
                                <div className="flex flex-wrap gap-1.5">
                                  {vs.write_methods.map((m) => (
                                    <span
                                      key={m.method}
                                      title={
                                        m.covered_by_mixin
                                          ? "Coberto pelo mixin"
                                          : m.has_explicit_invalidation
                                          ? "Invalidação explícita presente"
                                          : "⚠ Sem invalidação"
                                      }
                                      className={[
                                        "px-2 py-1 rounded-md text-xs font-mono font-semibold border",
                                        m.needs_attention
                                        ? "bg-red-500/10 text-red-400 border-red-500/20"
                                        : "bg-slate-700/50 text-slate-300 border-slate-600",
                                      ].join(" ")}
                                    >
                                      {m.method}
                                      {m.covered_by_mixin && " 🛡"}
                                      {!m.covered_by_mixin && m.has_explicit_invalidation && " ✓"}
                                      {m.needs_attention && " ⚠"}
                                    </span>
                                  ))}
                                </div>
                              )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <StatusBadge status={vs.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Issues destacados */}
              {fileResult.viewsets.some((v) => v.issues?.length > 0) && (
                <div className="px-5 py-4 bg-yellow-500/5 border-t border-yellow-500/15 text-sm text-yellow-400 space-y-2">
                  <div className="font-bold flex items-center gap-2">
                    <span className="text-lg">⚠</span> Ações sem invalidação de cache:
                  </div>
                  <ul className="list-disc list-inside pl-6 space-y-1">
                    {fileResult.viewsets.filter(v => v.issues?.length).map(v => (
                      <li key={v.name}>
                        <span className="font-mono font-semibold text-yellow-300">{v.name}</span>
                        {" → "}
                        {v.issues.join(", ")}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Seção 2: Probe Dinâmico ─────────────────────────────────────────────────

const DEFAULT_PROBE = {
  url: "",
  token: "",
  mutation_method: "POST",
  mutation_url: "",
  extra_headers: "",
  mutation_payload: "",
  timeout_s: "10",
};

function DynamicProbe() {
  const [form,    setForm]    = useState(DEFAULT_PROBE);
  const [loading, setLoading] = useState(false);
  const [report,  setReport]  = useState(null);
  const [error,   setError]   = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const run = async () => {
    if (!form.url.trim()) { setError("URL é obrigatória."); return; }
    if (!form.token.trim()) { setError("Token é obrigatório."); return; }
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      let extra_headers = {};
      if (form.extra_headers.trim()) {
        try { extra_headers = JSON.parse(form.extra_headers); }
        catch { setError("extra_headers deve ser JSON válido."); setLoading(false); return; }
      }
      let mutation_payload = {};
      if (form.mutation_payload.trim()) {
        try { mutation_payload = JSON.parse(form.mutation_payload); }
        catch { setError("mutation_payload deve ser JSON válido."); setLoading(false); return; }
      }
      const { data } = await axios.post("/autoauditor/api/audit/cache/", {
        url: form.url,
        token: form.token,
        mutation_method: form.mutation_method,
        mutation_url: form.mutation_url || undefined,
        extra_headers,
        mutation_payload,
        timeout_s: parseFloat(form.timeout_s) || 10,
      });
      setReport(data.report);
    } catch (e) {
      setError(e.response?.data?.error ?? e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Formulário */}
      <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="sm:col-span-2">
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">URL do endpoint (GET de listagem) *</label>
            <input
              value={form.url}
              onChange={(e) => set("url", e.target.value)}
              placeholder="http://localhost:8000/api/ferias-solicitacoes/"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">Token de autorização *</label>
            <input
              type="password"
              value={form.token}
              onChange={(e) => set("token", e.target.value)}
              placeholder="Bearer token ou API key"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">Extra headers (JSON)</label>
            <input
              value={form.extra_headers}
              onChange={(e) => set("extra_headers", e.target.value)}
              placeholder='{"X-Active-Profile-Code": "COORDENADOR"}'
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">Método da mutação</label>
            <select
              value={form.mutation_method}
              onChange={(e) => set("mutation_method", e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
            >
              {["POST", "PATCH", "PUT", "DELETE"].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">URL da mutação <span className="text-slate-500 font-normal">(padrão: mesma URL)</span></label>
            <input
              value={form.mutation_url}
              onChange={(e) => set("mutation_url", e.target.value)}
              placeholder="http://localhost:8000/api/ferias-solicitacoes/"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">Payload da mutação (JSON)</label>
            <textarea
              rows={3}
              value={form.mutation_payload}
              onChange={(e) => set("mutation_payload", e.target.value)}
              placeholder='{"servidor": 1, "data_inicio": "2026-03-01", "data_fim": "2026-03-10"}'
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 transition-all resize-y"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-1.5">Timeout (s)</label>
            <input
              type="number"
              value={form.timeout_s}
              onChange={(e) => set("timeout_s", e.target.value)}
              min={1} max={60}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
            />
          </div>
        </div>

        <div className="mt-6 pt-6 border-t border-slate-800">
          <button
            onClick={run}
            disabled={loading}
            className="w-full sm:w-auto px-8 py-3 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors flex items-center justify-center gap-2"
            style={{boxShadow:'0 0 16px rgba(99,102,241,0.3)'}}
          >
            {loading ? "Executando probe…" : "▶ Executar Probe de Cache"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm font-medium text-red-400">{error}</div>
      )}

      {report && (
        <div className="space-y-6">
          {/* Resumo do probe */}
          <div className={`rounded-xl border p-6 flex flex-wrap gap-8 items-center ${report.overall_passed ? "border-emerald-500/20 bg-emerald-500/5" : "border-red-500/20 bg-red-500/5"}`}>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Resultado geral</div>
              <div className={`text-2xl font-extrabold ${report.overall_passed ? "text-emerald-400" : "text-red-400"}`}>
                {report.overall_passed ? "✓ PASSOU" : "✗ FALHOU"}
              </div>
            </div>
            <div className="w-px h-12 bg-slate-700 hidden sm:block"></div>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Cache aquecido</div>
              <div className="mt-1"><PassBadge passed={report.warmup_ok} /></div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Invalidação confirmada</div>
              <div className="mt-1"><PassBadge passed={report.invalidation_ok} /></div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Speedup (frio/quente)</div>
              <div className="text-slate-100 font-mono font-bold text-lg">{report.speedup_ratio}×</div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">p50 GET</div>
              <div className="text-slate-100 font-mono font-bold text-lg">{report.latency_p50_ms} ms</div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">p95 GET</div>
              <div className="text-slate-100 font-mono font-bold text-lg">{report.latency_p95_ms} ms</div>
            </div>
          </div>

          {/* Passos */}
          <div className="bg-slate-900 border border-slate-700/50 rounded-xl overflow-hidden">
            <div className="px-5 py-4 bg-slate-800/50 border-b border-slate-700/50 text-xs text-slate-500 font-bold uppercase tracking-wider">
              Detalhes dos 4 passos
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-700/50 bg-slate-900">
                    <th className="text-center px-4 py-3">Passo</th>
                    <th className="text-center px-4 py-3">Método</th>
                    <th className="text-center px-4 py-3">HTTP</th>
                    <th className="text-center px-4 py-3">X-API-Cache</th>
                    <th className="text-center px-4 py-3">Esperado</th>
                    <th className="text-right px-5 py-3">Latência</th>
                    <th className="text-center px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {report.steps.map((step) => (
                    <tr key={step.step} className="hover:bg-slate-800/40 transition-colors">
                      <td className="text-center px-4 py-3 font-bold text-slate-400">{step.step}</td>
                      <td className="text-center px-4 py-3 font-mono text-xs font-semibold text-slate-400">{step.method}</td>
                      <td className="text-center px-4 py-3">
                        <span className={`font-mono font-bold ${step.status_code >= 400 ? "text-red-400" : "text-slate-300"}`}>
                          {step.status_code || "–"}
                        </span>
                      </td>
                      <td className="text-center px-4 py-3"><CacheStatusBadge value={step.cache_status} /></td>
                      <td className="text-center px-4 py-3">
                        {step.expected_cache
                          ? <CacheStatusBadge value={step.expected_cache} />
                          : <span className="text-slate-600 text-xs font-medium italic">–</span>}
                      </td>
                      <td className="text-right px-5 py-3 font-mono text-xs font-semibold text-slate-400">
                        {step.latency_ms > 0 ? `${step.latency_ms} ms` : "–"}
                      </td>
                      <td className="text-center px-4 py-3"><PassBadge passed={step.passed} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {report.steps.some((s) => s.note) && (
              <div className="px-5 py-4 bg-yellow-500/5 border-t border-yellow-500/15 text-sm text-yellow-400 space-y-1.5">
                {report.steps.filter((s) => s.note).map((s) => (
                  <div key={s.step} className="flex gap-2">
                    <span className="font-bold">Passo {s.step}:</span> 
                    <span>{s.note}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {report.error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm font-medium text-red-400">
              Erro: {report.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Componente raiz ─────────────────────────────────────────────────────────

const SUBTABS = [
  { id: "static",  label: "🔍 Auditoria Estática (AST)" },
  { id: "dynamic", label: "⚡ Probe Dinâmico" },
];

export default function CacheAudit() {
  const [sub, setSub] = useState("static");

  return (
    <div className="space-y-6 bg-white rounded-2xl p-8 border border-gray-200 shadow-sm">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Cache & Performance</h2>
      <p className="text-gray-600 text-sm mb-6">
        Analise a configuração de cache dos seus ViewSets ou execute testes dinâmicos para validar a invalidação.
      </p>

      {/* Subtabs */}
      <div className="flex gap-2 border-b border-gray-200 mb-6">
        {SUBTABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setSub(t.id)}
            className={[
              "px-5 py-2.5 text-sm font-semibold transition-colors -mb-px",
              sub === t.id
                ? "text-brand-600 border-b-2 border-brand-500"
                : "text-gray-500 hover:text-gray-800 hover:border-gray-300 border-b-2 border-transparent",
            ].join(" ")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {sub === "static"  && <StaticAudit />}
      {sub === "dynamic" && <DynamicProbe />}
    </div>
  );
}
