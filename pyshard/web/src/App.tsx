import React, { useState } from 'react'
import { Shard } from './types'
import { RepoInput } from './components/RepoInput'
import { ShardChecklist } from './components/ShardChecklist'
import { SynthesisPanel } from './components/SynthesisPanel'

export default function App() {
  const [shards, setShards] = useState<Shard[]>([])
  const [result, setResult] = useState<any>(null)

  const selectedShards = shards.filter(s => s.selected)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">PyShard-P9</h1>
          <p className="text-sm text-slate-400 mt-1">Python-centric reverse-engineering, SRP sharding, and synthesis engine</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <RepoInput onShardsLoaded={setShards} />
            {shards.length > 0 && (
              <ShardChecklist shards={shards} onChange={setShards} />
            )}
          </div>
          <div>
            <SynthesisPanel selectedShards={selectedShards} onSynthesized={setResult} />
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
