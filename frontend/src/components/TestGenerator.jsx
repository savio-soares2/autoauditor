import { useState, useEffect } from "react";
import axios from "axios";

/**
 * TestGenerator
 * -------------
 * Recebe um caminho de arquivo Python, chama a API /autoauditor/api/generate/test/,
 * exibe o resumo do AST extraído e o prompt final gerado.
 * O usuário pode copiar o prompt e colá-lo em qualquer IA (ChatGPT, Gemini, etc.)
 *
 * Props:
 *   prefilledFilePath – (opcional) pré-preenche o campo de arquivo
 *                       quando chamado a partir da CoverageMatrix
 */
export default function TestGenerator({ prefilledFilePath = "" }) {
  const [filePath,  setFilePath]  = useState(prefilledFilePath);
  const [framework, setFramework] = useState("django");
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState(null);
  const [copied,    setCopied]    = useState(false);

  // Sync quando o pai muda o prefilledFilePath (ex: clique em "Gerar Teste" na matrix)
  useEffect(() => {
    if (prefilledFilePath) {
      setFilePath(prefilledFilePath);
      setResult(null);
      setError(null);
    }
  }, [prefilledFilePath]);

  const handleGenerate = async () => {
    if (!filePath.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const { data } = await axios.post("/autoauditor/api/generate/test/", {
        file_path: filePath.trim(),
        framework,
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.prompt) return;
    await navigator.clipboard.writeText(result.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto bg-slate-900 rounded-2xl p-8 border border-slate-700/50" style={{boxShadow:'0 4px 32px rgba(0,0,0,0.4)'}}>
      <h2 className="text-2xl font-bold text-slate-100 mb-2">
        Gerador de Testes via AST
      </h2>
      <p className="text-slate-400 text-sm mb-6 leading-relaxed">
        Informe o caminho de um arquivo <code className="text-brand-400 bg-brand-500/10 px-1.5 py-0.5 rounded font-mono text-xs">.py</code> do
        seu projeto. O AutoAuditor extrairá apenas o <strong className="text-slate-200">esqueleto</strong> do código
        (classes, atributos e assinaturas de métodos) e gerará um prompt enxuto para a IA.
      </p>

      {/* Controls ----------------------------------------------------------- */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="Ex: /home/user/meu-projeto/app/models.py"
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50 font-mono transition-all"
        />
        <select
          value={framework}
          onChange={(e) => setFramework(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
        >
          <option value="django">Django</option>
          <option value="generic">Generic Python</option>
        </select>
        <button
          onClick={handleGenerate}
          disabled={loading || !filePath.trim()}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
        >
          {loading ? "Extraindo..." : "Gerar Prompt"}
        </button>
      </div>

      {/* Error -------------------------------------------------------------- */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 mb-6 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Results ------------------------------------------------------------ */}
      {result?.success && (
        <div className="space-y-6">
          {/* AST Summary */}
          <div className="bg-slate-800/60 rounded-xl p-6 border border-slate-700/50">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">
              Resumo do AST extraído
            </h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <Stat label="Classes" value={result.summary.classes} />
              <Stat label="Funções" value={result.summary.top_level_functions} />
              <Stat label="Imports" value={result.summary.imports} />
            </div>
            {result.summary.class_names?.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-700/50">
                {result.summary.class_names.map((name) => (
                  <span
                    key={name}
                    className="bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded-md px-2.5 py-1 text-xs font-mono font-semibold"
                  >
                    {name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Prompt Output */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 shadow-lg overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800 bg-gray-800/50">
              <span className="text-sm text-gray-300 font-semibold">
                Prompt gerado para IA
              </span>
              <button
                onClick={handleCopy}
                className="text-xs font-medium px-3.5 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-white transition-colors shadow-sm"
              >
                {copied ? "✓ Copiado!" : "Copiar prompt"}
              </button>
            </div>
            <pre className="text-green-400 text-sm p-5 overflow-auto max-h-[28rem] whitespace-pre-wrap leading-relaxed font-mono custom-scrollbar">
              {result.prompt}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4 text-center">
      <p className="text-3xl font-extrabold text-slate-100">{value}</p>
      <p className="text-slate-500 text-xs font-semibold uppercase tracking-wide mt-1">{label}</p>
    </div>
  );
}
