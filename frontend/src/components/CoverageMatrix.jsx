import { useState, useEffect } from "react";
import axios from "axios";

/**
 * CoverageMatrix
 * ---------------
 * Varre o projeto e exibe quais arquivos têm (ou não têm) testes correspondentes.
 *
 * Seções:
 *   • Barra de progresso de cobertura geral
 *   • Lista de arquivos SEM cobertura (vermelho) – com botão "Gerar Teste"
 *   • Lista de arquivos COM cobertura (verde)
 *   • Filtros por linguagem (Python / React) e estado (coberto / descoberto)
 */
export default function CoverageMatrix({ onGenerateTest }) {
  const [projectPath, setProjectPath] = useState("");
  const [data,        setData]        = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [filter,      setFilter]      = useState({ language: "all", status: "uncovered" });

  const fetchMatrix = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = projectPath.trim() ? { path: projectPath.trim() } : {};
      const { data: res } = await axios.get("/autoauditor/api/coverage/matrix/", { params });
      setData(res);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  // Carrega automaticamente ao montar
  useEffect(() => { fetchMatrix(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Filtragem ─────────────────────────────────────────────────────────────
  const allEntries = data
    ? [...(data.uncovered || []).map((e) => ({ ...e, covered: false })),
       ...(data.covered   || []).map((e) => ({ ...e, covered: true  }))]
    : [];

  const filtered = allEntries.filter((e) => {
    const langOk = filter.language === "all" || e.language === filter.language;
    const statusOk =
      filter.status === "all"
        ? true
        : filter.status === "covered" ? e.covered : !e.covered;
    return langOk && statusOk;
  });

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Matriz de Cobertura</h2>
        <p className="text-slate-400 text-sm">
          Arquivos do projeto e seus testes correspondentes. Clique em{" "}
          <strong className="text-brand-400 font-semibold">Gerar Teste</strong> para criar um prompt de IA
          para qualquer arquivo descoberto.
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={projectPath}
          onChange={(e) => setProjectPath(e.target.value)}
          placeholder="Caminho do projeto (deixe vazio = root do Django)"
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 font-mono transition-all"
        />
        <button
          onClick={fetchMatrix}
          disabled={loading}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
          style={{boxShadow:'0 0 16px rgba(99,102,241,0.25)'}}
        >
          {loading ? "Varrendo..." : "Varrer projeto"}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 text-sm font-medium">
          {error}
        </div>
      )}

      {data && (
        <>
          {/* ── Summary card ── */}
          <div className="bg-slate-900 rounded-xl border border-slate-700/50 p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-300 font-semibold text-lg">Cobertura geral</span>
              <span className="text-3xl font-extrabold text-brand-400">{data.coverage_pct}%</span>
            </div>
            <div className="h-2 bg-slate-700/60 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-700"
                style={{ width: `${data.coverage_pct}%`, boxShadow: '0 0 10px rgba(99,102,241,0.5)' }}
              />
            </div>
            <div className="flex justify-between text-sm font-medium text-slate-500 mt-3">
              <span className="text-emerald-400">✓ {data.covered_count} cobertos</span>
              <span>{data.total} arquivos totais</span>
              <span className="text-red-400">✗ {data.uncovered_count} descobertos</span>
            </div>
          </div>

          {/* ── Filters ── */}
          <div className="flex flex-wrap items-center gap-2 bg-slate-800/50 p-2 rounded-lg border border-slate-700/50">
            {[
              { label: "Todos",        value: "all",       group: "language" },
              { label: "🐍 Python",    value: "python",    group: "language" },
              { label: "⚛ React",     value: "react",     group: "language" },
            ].map((f) => (
              <FilterButton
                key={f.value}
                label={f.label}
                active={filter.language === f.value}
                onClick={() => setFilter((p) => ({ ...p, language: f.value }))}
              />
            ))}
            <div className="w-px h-6 bg-gray-300 mx-2" />
            {[
              { label: "Descobertos", value: "uncovered" },
              { label: "Cobertos",    value: "covered"   },
              { label: "Todos",       value: "all"        },
            ].map((f) => (
              <FilterButton
                key={f.value}
                label={f.label}
                active={filter.status === f.value}
                onClick={() => setFilter((p) => ({ ...p, status: f.value }))}
              />
            ))}
          </div>

          {/* ── File list ── */}
          {filtered.length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-12 bg-slate-800/30 border border-dashed border-slate-700 rounded-xl">
              Nenhum arquivo para exibir com os filtros selecionados.
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
              {filtered.map((entry) => (
                <FileRow
                  key={entry.path}
                  entry={entry}
                  onGenerateTest={onGenerateTest}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function FilterButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={[
        "px-4 py-1.5 text-sm font-medium rounded-md transition-all",
        active
          ? "bg-slate-700 text-slate-100 ring-1 ring-slate-600"
          : "text-slate-500 hover:text-slate-200 hover:bg-slate-700/50",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function FileRow({ entry, onGenerateTest }) {
  const langIcon  = entry.language === "python" ? "🐍" : "⚛";
  const isCovered = entry.covered;

  return (
    <div
      className={[
        "flex items-center justify-between rounded-xl px-5 py-3 border transition-all",
        isCovered
          ? "bg-emerald-500/5 border-emerald-500/15 hover:border-emerald-500/30"
          : "bg-red-500/5 border-red-500/15 hover:border-red-500/30",
      ].join(" ")}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-lg">{langIcon}</span>
        <span
          className={[
            "text-sm font-mono truncate font-medium",
            isCovered ? "text-slate-300" : "text-red-400",
          ].join(" ")}
        >
          {entry.path}
        </span>
        {isCovered && entry.test_file && (
          <span className="hidden sm:inline text-emerald-400 text-xs font-mono truncate bg-emerald-500/10 px-2 py-0.5 rounded">
            → {entry.test_file.split(/[\\/]/).pop()}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 shrink-0 ml-4">
        <span
          className={[
            "text-xs px-2.5 py-1 rounded-md font-bold uppercase tracking-wide",
            isCovered ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400",
          ].join(" ")}
        >
          {isCovered ? "✓ coberto" : "✗ sem teste"}
        </span>

        {!isCovered && entry.language === "python" && onGenerateTest && (
          <button
            onClick={() => onGenerateTest(entry.path)}
            className="text-xs font-semibold px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-md transition-colors"
            style={{boxShadow:'0 0 10px rgba(99,102,241,0.2)'}}
          >
            Gerar Teste
          </button>
        )}
      </div>
    </div>
  );
}
