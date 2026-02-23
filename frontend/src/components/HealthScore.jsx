import { useEffect, useState } from "react";
import axios from "axios";

/**
 * HealthScore
 * -----------
 * Medidor principal de saúde do projeto.
 * Exibe o score (0–100), a nota em letra (A→F), e os componentes:
 *   • Taxa de aprovação dos testes
 *   • Nota de segurança
 *   • Contagens por suite (Pytest / Vitest / Playwright)
 *   • Botão para forçar recálculo
 */
export default function HealthScore() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [recalc, setRecalc]   = useState(false);

  const fetchHealth = () => {
    setLoading(true);
    axios
      .get("/autoauditor/api/health/")
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchHealth(); }, []);

  const handleRecalc = () => {
    setRecalc(true);
    axios
      .post("/autoauditor/api/health/")
      .then(() => fetchHealth())
      .finally(() => setRecalc(false));
  };

  if (loading) return <Skeleton />;
  if (!data?.latest)
    return (
      <div className="text-slate-400 text-sm p-12 text-center bg-slate-900 rounded-2xl border border-slate-700/50">
        Nenhum dado ainda. Execute ao menos uma auditoria ou suite de testes.
        <br />
        <button
          onClick={handleRecalc}
          className="mt-6 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium rounded-lg transition-colors"
          style={{boxShadow:'0 0 16px rgba(99,102,241,0.3)'}}
        >
          Calcular agora
        </button>
      </div>
    );

  const h = data.latest;

  return (
    <div className="space-y-6">
      {/* ── Hero ── */}
      <div className="flex flex-col sm:flex-row items-center gap-10 bg-slate-900 rounded-2xl p-8 border border-slate-700/50" style={{boxShadow:'0 4px 32px rgba(0,0,0,0.4)'}}>
        <GaugeDial score={h.score} grade={h.grade} />

        <div className="flex-1 space-y-6 w-full">
          <div className="grid grid-cols-2 gap-4">
            <Metric label="Taxa de Testes" value={`${h.test_pass_rate}%`} color="text-blue-600" />
            <Metric label="Nota de Segurança" value={`${h.security_score}/100`} color="text-purple-600" />
          </div>

          {/* Barra de progresso de cobertura */}
          <div>
            <div className="flex justify-between text-sm font-medium text-slate-400 mb-2">
              <span>Cobertura de arquivos</span>
              <span>
                {h.covered_count} / {h.covered_count + h.uncovered_count} arquivos
              </span>
            </div>
            <div className="h-2 bg-slate-700/60 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-700"
                style={{boxShadow:'0 0 10px rgba(99,102,241,0.5)'}}
                style={{
                  width: `${
                    h.covered_count + h.uncovered_count > 0
                      ? (h.covered_count / (h.covered_count + h.uncovered_count)) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Suites ── */}
      <div className="grid grid-cols-3 gap-4">
        <SuiteCard icon="🐍" label="Pytest" passed={h.pytest_passed} total={h.pytest_total} />
        <SuiteCard icon="⚡" label="Vitest" passed={h.vitest_passed} total={h.vitest_total} />
        <SuiteCard icon="🎭" label="Playwright" passed={h.playwright_passed} total={h.playwright_total} />
      </div>

      {/* ── Ações ── */}
      <div className="flex justify-between items-center pt-2">
        <p className="text-slate-500 text-xs font-mono">
          Último cálculo: {new Date(h.created_at).toLocaleString("pt-BR")}
        </p>
        <button
          onClick={handleRecalc}
          disabled={recalc}
          className="px-4 py-2 bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {recalc ? "Recalculando..." : "↻ Recalcular agora"}
        </button>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-48 bg-slate-800/60 rounded-2xl" />
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => <div key={i} className="h-24 bg-slate-800/60 rounded-xl" />)}
      </div>
    </div>
  );
}

function GaugeDial({ score, grade }) {
  // SVG arc gauge  (semicircle)
  const radius   = 56;
  const cx       = 72;
  const cy       = 72;
  const startAngle = -180;
  const endAngle   = 0;
  const pct        = Math.max(0, Math.min(100, score));
  const angle      = startAngle + (pct / 100) * 180;

  const polar = (deg, r = radius) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const gradeColors = { A: "#16a34a", B: "#65a30d", C: "#ca8a04", D: "#ea580c", F: "#dc2626" };
  const color = gradeColors[grade] || "#9ca3af";

  const start = polar(startAngle);
  const end   = polar(endAngle);
  const needle = polar(angle, 48);

  return (
    <div className="shrink-0 flex flex-col items-center">
      <svg width={144} height={90} viewBox="0 0 144 85">
        {/* Track */}
        <path
          d={`M ${start.x} ${start.y} A ${radius} ${radius} 0 0 1 ${end.x} ${end.y}`}
          fill="none" stroke="#1e293b" strokeWidth={10} strokeLinecap="round"
        />
        {/* Progress arc */}
        {pct > 0 && (
          <path
            d={`M ${start.x} ${start.y} A ${radius} ${radius} 0 ${pct > 50 ? 1 : 0} 1 ${needle.x} ${needle.y}`}
            fill="none" stroke={color} strokeWidth={10} strokeLinecap="round"
          />
        )}
        {/* Needle */}
        <line x1={cx} y1={cy} x2={needle.x} y2={needle.y} stroke={color} strokeWidth={3} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={4} fill={color} />
      </svg>
      <p className="text-4xl font-bold text-slate-100 mt-2">{score}</p>
      <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mt-1">Health Score</p>
      <span className="mt-3 text-lg font-bold px-4 py-1 rounded-md bg-transparent" style={{ color, border: `1px solid ${color}60`, boxShadow: `0 0 12px ${color}30` }}>
        {grade}
      </span>
    </div>
  );
}

function Metric({ label, value, color }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      <p className="text-slate-400 text-sm font-medium mt-1">{label}</p>
    </div>
  );
}

function SuiteCard({ icon, label, passed, total }) {
  const pct = total > 0 ? Math.round((passed / total) * 100) : null;
  const color = pct === null ? "text-gray-400" : pct >= 80 ? "text-green-600" : pct >= 50 ? "text-yellow-600" : "text-red-600";
  return (
    <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-5 transition-all hover:border-slate-600">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{icon}</span>
        <span className="text-sm font-semibold text-slate-300">{label}</span>
      </div>
      {pct !== null ? (
        <>
          <p className={`text-3xl font-bold ${color}`}>{pct}%</p>
          <p className="text-slate-500 text-sm font-medium mt-1">{passed}/{total} testes</p>
        </>
      ) : (
        <p className="text-slate-600 text-sm font-medium mt-2">Sem dados</p>
      )}
    </div>
  );
}
