import { useEffect, useState } from "react";
import axios from "axios";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";

/**
 * TrendChart
 * ----------
 * Gráfico de linhas mostrando a evolução do Health Score ao longo do tempo.
 * Usa recharts LineChart com dados vindos de /autoauditor/api/health/.
 *
 * Também renderiza o histórico de resultados de testes por suite.
 */
export default function TrendChart() {
  const [healthData, setHealthData]   = useState([]);
  const [testData,   setTestData]     = useState({ pytest: [], vitest: [], playwright: [] });
  const [activeTab,  setActiveTab]    = useState("health");
  const [loading,    setLoading]      = useState(true);

  useEffect(() => {
    Promise.all([
      axios.get("/autoauditor/api/health/?limit=60"),
      axios.get("/autoauditor/api/history/tests/?limit=60"),
    ]).then(([healthRes, testRes]) => {
      // Health history
      const hd = (healthRes.data.history || []).map((h) => ({
        date:     new Date(h.created_at).toLocaleDateString("pt-BR"),
        score:    h.score,
        testes:   h.test_pass_rate,
        segurança: h.security_score,
      }));
      setHealthData(hd);

      // Test runs by type
      const runs = testRes.data.results || [];
      const pytest     = runs.filter((r) => r.run_type === "pytest").reverse()
        .map((r) => ({ date: new Date(r.created_at).toLocaleDateString("pt-BR"), pass_rate: r.pass_rate, passed: r.passed, total: r.total }));
      const vitest     = runs.filter((r) => r.run_type === "vitest").reverse()
        .map((r) => ({ date: new Date(r.created_at).toLocaleDateString("pt-BR"), pass_rate: r.pass_rate, passed: r.passed, total: r.total }));
      const playwright = runs.filter((r) => r.run_type === "playwright").reverse()
        .map((r) => ({ date: new Date(r.created_at).toLocaleDateString("pt-BR"), pass_rate: r.pass_rate, passed: r.passed, total: r.total }));
      setTestData({ pytest, vitest, playwright });
    }).catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const TABS = [
    { id: "health",     label: "Health Score" },
    { id: "pytest",     label: "Pytest" },
    { id: "vitest",     label: "Vitest" },
    { id: "playwright", label: "Playwright" },
  ];

  return (
    <div className="bg-slate-900 rounded-2xl p-8 border border-slate-700/50" style={{boxShadow:'0 4px 32px rgba(0,0,0,0.4)'}}>
      <h2 className="text-xl font-bold text-slate-100 mb-6">
        Histórico & Tendências
      </h2>

      {/* Sub-tabs */}
      <div className="flex gap-2 mb-8 border-b border-slate-700/60">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              "px-4 py-2.5 text-sm font-medium transition-colors -mb-px",
              activeTab === tab.id
                ? "border-b-2 border-brand-400 text-brand-400"
                : "text-slate-500 hover:text-slate-300 border-b-2 border-transparent",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <div className="h-64 bg-slate-800/60 rounded-xl animate-pulse" />}

      {!loading && activeTab === "health" && (
        <HealthLineChart data={healthData} />
      )}
      {!loading && activeTab === "pytest" && (
        <TestLineChart data={testData.pytest} label="Pytest" color="#6366f1" />
      )}
      {!loading && activeTab === "vitest" && (
        <TestLineChart data={testData.vitest} label="Vitest" color="#10b981" />
      )}
      {!loading && activeTab === "playwright" && (
        <TestLineChart data={testData.playwright} label="Playwright" color="#f59e0b" />
      )}
    </div>
  );
}

// ── Sub-charts ─────────────────────────────────────────────────────────────────

const TOOLTIP_STYLE = {
  backgroundColor: "#0f172a",
  border: "1px solid #334155",
  borderRadius: 8,
  fontSize: 12,
  color: "#e2e8f0",
  boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
};

function HealthLineChart({ data }) {
  if (!data.length)
    return <EmptyState message="Nenhum dado de Health Score ainda." />;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 12, paddingTop: "20px", color: '#94a3b8' }} />
        <ReferenceLine y={80} stroke="#22c55e" strokeDasharray="4 4" label={{ value: "Meta 80", fill: "#22c55e", fontSize: 10 }} />
        <Line type="monotone" dataKey="score"     name="Health Score"   stroke="#0ea5e9" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="testes"    name="Taxa de Testes %" stroke="#818cf8" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="segurança" name="Seg. Score"    stroke="#22c55e" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function TestLineChart({ data, label, color }) {
  if (!data.length)
    return <EmptyState message={`Nenhuma execução de ${label} registrada.`} />;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v, n, props) =>
            n === "pass_rate"
              ? [`${v}%  (${props.payload.passed}/${props.payload.total})`, "Pass Rate"]
              : [v, n]
          }
        />
        <ReferenceLine y={80} stroke="#22c55e" strokeDasharray="4 4" />
        <Line type="monotone" dataKey="pass_rate" name="Pass Rate %" stroke={color} strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function EmptyState({ message }) {
  return (
    <div className="h-48 flex items-center justify-center text-slate-500 text-sm bg-slate-800/30 rounded-xl border border-slate-700/50 border-dashed">
      {message}
    </div>
  );
}
