import React, { useState, useCallback } from 'react'
import { Sparkles, Loader2, AlertTriangle, CheckCircle, FileCode, ChevronDown, ChevronUp } from 'lucide-react'
import { Shard, SynthesisResult } from '../types'

export function SynthesisPanel({ selectedShards, onSynthesized }: { selectedShards: Shard[]; onSynthesized: (result: SynthesisResult) => void }) {
  const [description, setDescription] = useState('')
  const [projectName, setProjectName] = useState('my_synthesized_app')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState('')
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [error, setError] = useState('')
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set())

  const handleSynthesize = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setResult(null)
    if (!selectedShards.length) return
    if (!description.trim()) return

    setLoading(true)
    try {
      setStep('Analyzing gaps and dependencies...')
      await new Promise(r => setTimeout(r, 500))
      const res = await fetch('/api/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shard_ids: selectedShards.map(s => s.shard_id),
          description: description.trim(),
          project_name: projectName.trim() || 'synthesized_project',
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Synthesis failed')
      const data = await res.json()
      setResult(data)
      onSynthesized(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
      setStep('')
    }
  }

  const toggleFile = (path: string) => {
    const next = new Set(expandedFiles)
    if (next.has(path)) next.delete(path) else next.add(path)
    setExpandedFiles(next)
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-indigo-400" /> Step 3: Synthesize App
      </h2>

      <form onSubmit={handleSynthesize} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Project Name</label>
          <input
            value={projectName}
            onChange={e => setProjectName(e.target.value)}
            className="w-full p-2.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">App Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Describe the app you want to build from these shards..."
            rows={4}
            className="w-full p-2.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !selectedShards.length || !description.trim()}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2"
        >
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> {step || 'Synthesizing...'}</> : 'Generate Project'}
        </button>
      </form>

      {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center gap-2 text-sm text-emerald-400">
            <CheckCircle className="w-4 h-4" /> Project generated at: <code className="text-xs bg-slate-950 px-2 py-1 rounded">{result.output_path}</code>
          </div>

          {result.gaps.length > 0 && (
            <div className="bg-amber-950/30 border border-amber-800 rounded-lg p-4">
              <h3 className="text-sm font-bold text-amber-400 flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4" /> Identified Gaps
              </h3>
              <ul className="space-y-1">
                {result.gaps.map((g, i) => (
                  <li key={i} className="text-xs text-amber-200">
                    <span className="font-mono uppercase text-[10px] text-amber-500">{g.type}</span>: {g.description}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 className="text-sm font-bold text-slate-300 mb-2">Generated Files</h3>
            <div className="space-y-1">
              {result.files.map((f, i) => (
                <div key={i} className="border border-slate-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() => toggleFile(f.path)}
                    className="w-full flex items-center gap-2 p-2.5 bg-slate-950 hover:bg-slate-900 text-left"
                  >
                    <FileCode className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-mono text-slate-300 flex-1">{f.path}</span>
                    <span className="text-[10px] text-slate-500">{f.purpose}</span>
                    {expandedFiles.has(f.path) ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                  </button>
                  {expandedFiles.has(f.path) && (
                    <pre className="p-3 bg-slate-950 text-xs text-slate-400 overflow-x-auto max-h-64 font-mono border-t border-slate-800">
                      {f.content}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
