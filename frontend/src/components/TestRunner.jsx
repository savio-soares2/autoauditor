import { useState } from "react";
import axios from "axios";

const TOOLS = [
  {
    id: "pytest",
    label: "Pytest",
    icon: "🐍",
    description: "Testes unitários do backend Django",
    hint: "Requer: pip install pytest pytest-django pytest-json-report",
    bodyKey: "path",
    placeholder: "Ex: /home/user/meu-projeto  (diretório com manage.py)",
  },
  {
    id: "vitest",
    label: "Vitest",
    icon: "⚡",
    description: "Testes unitários dos componentes React",
    hint: "Requer: npm install -D vitest @testing-library/react",
    bodyKey: "path",
    placeholder: "Ex: /home/user/meu-projeto/frontend",
  },
  {
    id: "playwright",
    label: "Playwright",
    icon: "🎭",
    description: "Testes E2E (End-to-End) com navegador real",
    hint: "Requer: npx playwright install",
    bodyKey: "path",
    placeholder: "Ex: /home/user/meu-projeto  (onde está playwright.config.js)",
  },
];

/**
 * TestRunner
 * ----------
 * Permite executar Pytest, Vitest ou Playwright diretamente do painel.
 * Os resultados são salvos no banco via API e o health score é atualizado.
 */
export default function TestRunner() {
  const [selectedTool, setSelectedTool] = useState("pytest");
  const [targetPath,   setTargetPath]   = useState("");
  const [loading,      setLoading]      = useState(false);
  const [result,       setResult]       = useState(null);
  const [error,        setError]        = useState(null);

  const tool = TOOLS.find((t) => t.id === selectedTool);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const body = { tool: selectedTool };
      if (targetPath.trim()) body.path = targetPath.trim();

      const { data } = await axios.post("/autoauditor/api/run/tests/", body);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">
          Executar Suite de Testes
        </h2>
        <p className="text-slate-400 text-sm">
          Escolha a ferramenta, configure o caminho e clique em Executar.
          Os resultados serão salvos no banco e o Health Score será atualizado.
        </p>
      </div>

      {/* Tool selector */}
      <div className="grid grid-cols-3 gap-4">
        {TOOLS.map((t) => (
          <button
            key={t.id}
            onClick={() => { setSelectedTool(t.id); setResult(null); setError(null); }}
            className={[
              "rounded-xl p-5 border text-left transition-all",
              selectedTool === t.id
                ? "border-brand-500/60 bg-brand-500/10 ring-1 ring-brand-500/30"
                : "border-slate-700/60 bg-slate-900 hover:border-slate-600 hover:bg-slate-800/50",
            ].join(" ")}
          >
            <p className="text-2xl mb-2">{t.icon}</p>
            <p className="text-sm font-bold text-slate-200">{t.label}</p>
            <p className="text-slate-500 text-xs mt-1 leading-relaxed">{t.description}</p>
          </button>
        ))}
      </div>

      {/* Config */}
      <div className="bg-slate-900 rounded-xl border border-slate-700/50 p-6 space-y-5">
        <div>
          <label className="text-slate-300 text-sm font-semibold block mb-1.5">Diretório do projeto</label>
          <input
            type="text"
            value={targetPath}
            onChange={(e) => setTargetPath(e.target.value)}
            placeholder={tool.placeholder}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 font-mono transition-all"
          />
        </div>
        <p className="text-xs text-slate-600 font-medium">{tool.hint}</p>
        <button
          onClick={handleRun}
          disabled={loading}
          className="w-full py-3 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Spinner /> Executando {tool.label}...
            </>
          ) : (
            `${tool.icon} Executar ${tool.label}`
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Result */}
      {result?.success && <RunResult run={result.summary} tool={result.tool} />}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function RunResult({ run, tool }) {
  const passColor =
    run.pass_rate >= 80 ? "text-green-600" : run.pass_rate >= 50 ? "text-yellow-600" : "text-red-600";

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-700/50 p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-slate-100 font-bold text-lg">Resultado – {tool}</h3>
        <span className={`text-3xl font-extrabold ${passColor}`}>{run.pass_rate}%</span>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-5">
        <Stat label="Total"   value={run.total}   color="text-slate-200" />
        <Stat label="Passou"  value={run.passed}  color="text-emerald-400" />
        <Stat label="Falhou"  value={run.failed}  color="text-red-400" />
        <Stat label="Pulou"   value={run.skipped} color="text-yellow-400" />
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-slate-700/60 rounded-full overflow-hidden">
        <div
          className={[
            "h-full rounded-full transition-all duration-700",
            run.pass_rate >= 80 ? "bg-emerald-500" : run.pass_rate >= 50 ? "bg-yellow-500" : "bg-red-500",
          ].join(" ")}
          style={{ width: `${run.pass_rate}%` }}
        />
      </div>

      <div className="flex justify-between text-xs text-slate-600 mt-3 font-mono">
        <span>ID: #{run.id}</span>
        <span>{run.duration_seconds?.toFixed(2)}s</span>
      </div>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/40 rounded-lg p-3 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-slate-500 text-xs font-medium mt-1">{label}</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
    </svg>
  );
}
