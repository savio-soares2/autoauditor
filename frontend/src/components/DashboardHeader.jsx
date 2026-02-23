import { useEffect, useState } from "react";
import axios from "axios";

export default function DashboardHeader() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    axios
      .get("/autoauditor/api/status/")
      .then((res) => setStatus(res.data))
      .catch(() => setStatus({ status: "error" }));
  }, []);

  const toolBadge = (name, ok) => (
    <span
      key={name}
      className={[
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold font-mono border",
        ok ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20",
      ].join(" ")}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`} style={ok ? {boxShadow:'0 0 6px #34d399'} : {}}></span>
      {name}
    </span>
  );

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-8 py-3.5 flex items-center justify-between z-10" style={{boxShadow:'0 4px 24px rgba(0,0,0,0.3)'}}>
      <div className="flex items-center gap-2">
        <div className="w-1.5 h-5 rounded-full bg-brand-500" style={{boxShadow:'0 0 10px rgba(99,102,241,0.8)'}} />
        <span className="text-slate-200 font-semibold text-sm tracking-wide">Visão Geral</span>
      </div>

      {status && status.status === "ok" && (
        <div className="flex items-center gap-2">
          <span className="text-slate-500 text-xs font-medium mr-1">Ferramentas:</span>
          {Object.entries(status.tools).map(([name, ok]) =>
            toolBadge(name, ok)
          )}
        </div>
      )}
      {status && status.status === "error" && (
        <span className="text-xs font-medium text-red-400 bg-red-500/10 px-3 py-1 rounded-md border border-red-500/20">
          API Django offline
        </span>
      )}
    </header>
  );
}
