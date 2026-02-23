import { useState, useEffect } from "react";
import axios from "axios";
import DashboardHeader from "./components/DashboardHeader";
import HealthScore     from "./components/HealthScore";
import TrendChart      from "./components/TrendChart";
import TestRunner      from "./components/TestRunner";
import CoverageMatrix  from "./components/CoverageMatrix";
import AuditPanel      from "./components/AuditPanel";
import TestGenerator   from "./components/TestGenerator";
import CacheAudit      from "./components/CacheAudit";

const TABS = [
  { id: "health",    label: "❤️  Health Score"      },
  { id: "trends",    label: "📈 Tendências"          },
  { id: "runner",    label: "▶  Executar Testes"     },
  { id: "matrix",    label: "🗺  Cobertura"          },
  { id: "audit-dj",  label: "🐍 Auditoria Django"   },
  { id: "audit-fe",  label: "📦 Auditoria Frontend"  },
  { id: "test-gen",  label: "🤖 Fábrica de Testes"  },
  { id: "cache",     label: "🗄  Cache & Performance" },
];

export default function App() {
  const [activeTab,     setActiveTab]     = useState("health");
  const [prefilledFile, setPrefilledFile] = useState("");
  // Paths pré-configurados vindos da API Django
  const [paths,         setPaths]         = useState({ backend: "", frontend: "" });

  useEffect(() => {
    axios.get("/autoauditor/api/status/")
      .then((res) => {
        if (res.data?.paths) setPaths(res.data.paths);
      })
      .catch(() => {});
  }, []);

  const handleGenerateFromMatrix = (filePath) => {
    setPrefilledFile(filePath);
    setActiveTab("test-gen");
  };

  return (
    <div className="min-h-screen flex font-sans text-slate-100" style={{backgroundColor: '#07091d'}}>
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col z-10" style={{boxShadow: '4px 0 24px rgba(0,0,0,0.4)'}}>
        <div className="p-6 border-b border-slate-800 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm" style={{boxShadow: '0 0 16px rgba(99,102,241,0.4)'}}>
            AA
          </div>
          <div>
            <h1 className="text-slate-100 font-bold text-base leading-tight tracking-tight">
              AutoAuditor
            </h1>
            <p className="text-slate-500 text-xs font-medium">DevSecOps Dashboard</p>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <ul className="space-y-0.5">
            {TABS.map((tab) => (
              <li key={tab.id}>
                <button
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-3",
                    activeTab === tab.id
                      ? "bg-brand-500/10 text-brand-400 border border-brand-500/25"
                      : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="px-4 py-5 border-t border-slate-800">
          <p className="text-slate-600 text-xs font-mono">v1.0 · AutoAuditor</p>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <DashboardHeader />
        
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto">
            {activeTab === "health" && <HealthScore />}

            {activeTab === "trends" && <TrendChart />}

            {activeTab === "runner" && <TestRunner paths={paths} />}

            {activeTab === "matrix" && (
              <CoverageMatrix
                paths={paths}
                onGenerateTest={handleGenerateFromMatrix}
              />
            )}

            {activeTab === "audit-dj" && (
              <AuditPanel
                title="Auditoria de Segurança – Django (bandit)"
                apiEndpoint="/autoauditor/api/audit/django/"
                bodyKey="path"
                defaultValue={paths.backend}
                bodyPlaceholder="Caminho do backend Django"
              />
            )}

            {activeTab === "audit-fe" && (
              <AuditPanel
                title="Auditoria de Segurança – Frontend (npm audit)"
                apiEndpoint="/autoauditor/api/audit/frontend/"
                bodyKey="path"
                defaultValue={paths.frontend}
                bodyPlaceholder="Caminho do frontend React"
              />
            )}

            {activeTab === "test-gen" && (
              <TestGenerator prefilledFilePath={prefilledFile} basePath={paths.backend} />
            )}

            {activeTab === "cache" && <CacheAudit />}
          </div>
        </main>
      </div>
    </div>
  );
}

