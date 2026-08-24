import React, { useState } from 'react'
import { Shard, SynthesisResult } from './types'
import { RepoInput } from './components/RepoInput'
import { ShardChecklist } from './components/ShardChecklist'
import { SynthesisPanel } from './components/SynthesisPanel'

type SynthesisMode = 'python' | 'web-to-app'

export default function App() {
  const [shards, setShards] = useState<Shard[]>([])
  const [result, setResult] = useState<any>(null)
  const [mode, setMode] = useState<SynthesisMode>('python')

  const selectedShards = shards.filter(s => s.selected)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">PyShard-P9</h1>
          <p className="text-sm text-slate-400 mt-1">Python-centric reverse-engineering, SRP sharding, and synthesis engine</p>
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => setMode('python')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mode === 'python' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Python Project
            </button>
            <button
              onClick={() => setMode('web-to-app')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mode === 'web-to-app' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              WebToApp Module
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <RepoInput onShardsLoaded={setShards} />
            {shards.length > 0 && (
              <ShardChecklist shards={shards} onChange={setShards} />
            )}
          </div>
          <div>
            <SynthesisPanel selectedShards={selectedShards} onSynthesized={setResult} mode={mode} />
          </div>
        </div>

        {result && (
          <div className="mt-8 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="text-lg font-bold text-white mb-2">Synthesis Complete</h3>
            <pre className="text-xs text-slate-400 bg-slate-950 p-4 rounded-lg overflow-x-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
