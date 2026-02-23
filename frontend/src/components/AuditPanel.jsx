import { useState } from "react";
import axios from "axios";

/**
 * AuditPanel
 * ----------
 * Componente reutilizável para painéis de auditoria (bandit / npm audit).
 * Props:
 *   title          – Título do painel
 *   apiEndpoint    – URL da API Django (ex: /autoauditor/api/audit/django/)
 *   bodyKey        – Chave do body JSON a enviar (ex: "path")
 *   bodyPlaceholder – Placeholder do campo de input
 */
export default function AuditPanel({ title, apiEndpoint, bodyKey, bodyPlaceholder }) {
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const body = inputValue.trim() ? { [bodyKey]: inputValue.trim() } : {};
      const { data } = await axios.post(apiEndpoint, body);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  };

  // ── Issue summary ──────────────────────────────────────────────────────────
  const renderSummary = () => {
    if (!result) return null;

    // bandit
    if (result.report?.metrics) {
      const metrics = result.report.metrics;
      const totals = metrics["_totals"] || {};
      return (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {["SEVERITY.LOW", "SEVERITY.MEDIUM", "SEVERITY.HIGH"].map((key) => {
            const label = key.split(".")[1];
            const count = totals[key] ?? 0;
            const color =
              label === "HIGH"
                ? "text-red-400 bg-red-500/10 border-red-500/20"
                : label === "MEDIUM"
                ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20"
                : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
            return (
              <div key={key} className={`rounded-xl p-4 border ${color}`}>
                <p className="text-3xl font-extrabold">{count}</p>
                <p className="text-sm font-semibold mt-1 uppercase tracking-wide">{label}</p>
              </div>
            );
          })}
        </div>
      );
    }

    // npm audit
    if (result.total_vulnerabilities !== undefined) {
      const vuln = result.report?.metadata?.vulnerabilities || {};
      const colors = {
        critical: "text-red-400 bg-red-500/10 border-red-500/20",
        high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
        moderate: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
        low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
        info: "text-blue-400 bg-blue-500/10 border-blue-500/20",
      };
      return (
        <div className="grid grid-cols-5 gap-3 mb-6">
          {Object.entries(vuln).map(([level, count]) => (
            <div key={level} className={`rounded-xl p-4 border ${colors[level] || "bg-slate-800 border-slate-700 text-slate-400"}`}>
              <p className="text-2xl font-extrabold">{count}</p>
              <p className="text-xs font-semibold mt-1 capitalize">{level}</p>
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  // ── Issues list ────────────────────────────────────────────────────────────
  const renderIssues = () => {
    if (!result?.report?.results?.length) return null;
    return (
      <div className="space-y-3">
        <h3 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-3">
          Issues encontrados ({result.report.results.length})
        </h3>
        {result.report.results.map((issue, idx) => (
          <div
            key={idx}
            className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50 hover:border-slate-600 transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-bold text-slate-200">{issue.test_id} – {issue.test_name}</p>
              <span
                className={[
                  "text-xs px-2.5 py-1 rounded-md font-bold tracking-wide shrink-0",
                  issue.issue_severity === "HIGH"
                    ? "bg-red-500/15 text-red-400"
                    : issue.issue_severity === "MEDIUM"
                    ? "bg-yellow-500/15 text-yellow-400"
                    : "bg-emerald-500/15 text-emerald-400",
                ].join(" ")}
              >
                {issue.issue_severity}
              </span>
            </div>
            <p className="text-slate-400 text-sm mt-2 leading-relaxed">{issue.issue_text}</p>
            <p className="text-slate-600 text-xs mt-2 font-mono bg-slate-900 inline-block px-2 py-1 rounded border border-slate-700/50">
              {issue.filename}:{issue.line_number}
            </p>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto bg-slate-900 rounded-2xl p-8 border border-slate-700/50" style={{boxShadow:'0 4px 32px rgba(0,0,0,0.4)'}}>
      <h2 className="text-2xl font-bold text-slate-100 mb-6">{title}</h2>

      {/* Input + Button */}
      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={bodyPlaceholder}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 font-mono transition-all"
        />
        <button
          onClick={handleRun}
          disabled={loading}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
          style={{boxShadow:'0 0 16px rgba(99,102,241,0.25)'}}
        >
          {loading ? "Analisando..." : "Executar Auditoria"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 mb-6 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Results */}
      {result && result.success && (
        <div>
          {renderSummary()}
          {renderIssues()}

          {/* Raw JSON viewer */}
          <details className="mt-6">
            <summary className="text-gray-500 text-sm font-medium cursor-pointer hover:text-gray-700 select-none">
              Ver JSON completo
            </summary>
            <pre className="mt-3 bg-gray-900 text-green-400 text-xs p-5 rounded-xl overflow-auto max-h-96 border border-gray-800 shadow-inner custom-scrollbar">
              {JSON.stringify(result.report, null, 2)}
            </pre>
          </details>
        </div>
      )}

      {result && !result.success && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 text-sm font-medium mt-6">
          {result.error}
        </div>
      )}
    </div>
  );
}
