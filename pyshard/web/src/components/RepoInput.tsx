import React, { useState, useCallback } from 'react'
import { Upload, CheckCircle2, Circle, Loader2, X } from 'lucide-react'
import { Shard } from '../types'

export function RepoInput({ onShardsLoaded }: { onShardsLoaded: (shards: Shard[]) => void }) {
  const [urls, setUrls] = useState('')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState('')
  const [error, setError] = useState('')

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const repoList = urls.split('\n').map(u => u.trim()).filter(Boolean)
    if (!repoList.length) return

    setLoading(true)
    setStep('Cloning repositories...')
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_urls: repoList }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Ingest failed')
      const data = await res.json()
      setStep('Sharding Python files...')
      const shardRes = await fetch('/api/shard', { method: 'POST' })
      if (!shardRes.ok) throw new Error((await shardRes.json()).detail || 'Shard failed')
      const shardData = await shardRes.json()
      setStep(`Loaded ${shardData.total_shards} shards`)
      const listRes = await fetch('/api/shards')
      const listData = await listRes.json()
      onShardsLoaded(listData.shards.map((s: any) => ({ ...s, selected: false })))
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
        <Upload className="w-5 h-5 text-indigo-400" /> Step 1: Input Repositories
      </h2>
      <form onSubmit={handleIngest} className="space-y-4">
        <textarea
          value={urls}
          onChange={e => setUrls(e.target.value)}
          placeholder="https://github.com/user/repo1&#10;https://github.com/user/repo2"
          className="w-full h-32 p-3 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2"
        >
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> {step}</> : 'Ingest & Shard'}
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </div>
  )
}
