import React, { useState, useMemo } from 'react'
import { CheckCircle2, Circle, Search, Filter } from 'lucide-react'
import { Shard } from '../types'

export function ShardChecklist({ shards, onChange }: { shards: Shard[]; onChange: (s: Shard[]) => void }) {
  const [filter, setFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')

  const categories = useMemo(() => {
    const cats = new Set(shards.map(s => s.category))
    return ['all', ...Array.from(cats)]
  }, [shards])

  const filtered = useMemo(() => {
    return shards.filter(s => {
      const matchesText = s.name.toLowerCase().includes(filter.toLowerCase()) || s.description.toLowerCase().includes(filter.toLowerCase())
      const matchesCat = categoryFilter === 'all' || s.category === categoryFilter
      return matchesText && matchesCat
    })
  }, [shards, filter, categoryFilter])

  const toggle = (id: string) => {
    onChange(shards.map(s => s.shard_id === id ? { ...s, selected: !s.selected } : s))
  }

  const toggleAll = () => {
    const allSelected = filtered.every(s => s.selected)
    onChange(shards.map(s => {
      const inFiltered = filtered.some(f => f.shard_id === s.shard_id)
      return { ...s, selected: inFiltered ? !allSelected : s.selected }
    }))
  }

  const selectedCount = shards.filter(s => s.selected).length

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Filter className="w-5 h-5 text-indigo-400" /> Step 2: Select Shards
        </h2>
        <span className="text-xs text-slate-400">{selectedCount} selected</span>
      </div>

      <div className="flex gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Search shards..."
            className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button onClick={toggleAll} className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 rounded-lg">
          {filtered.every(s => s.selected) ? 'Deselect All' : 'Select All'}
        </button>
      </div>

      <div className="max-h-96 overflow-y-auto space-y-1 pr-1">
        {filtered.map(shard => (
          <div
            key={shard.shard_id}
            onClick={() => toggle(shard.shard_id)}
            className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer border transition-colors ${
              shard.selected ? 'bg-indigo-950/40 border-indigo-800' : 'bg-slate-950 border-slate-800 hover:border-slate-700'
            }`}
          >
            {shard.selected ? <CheckCircle2 className="w-5 h-5 text-indigo-400 mt-0.5" /> : <Circle className="w-5 h-5 text-slate-600 mt-0.5" />}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-200 truncate">{shard.name}</span>
                <span className="px-1.5 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-mono rounded">{shard.shard_type}</span>
                <span className="px-1.5 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-mono rounded">{shard.category}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1 line-clamp-2">{shard.description}</p>
              <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500 font-mono">
                <span>complexity: {shard.cyclomatic_complexity}</span>
                <span>imports: {shard.import_dependencies.slice(0, 3).join(', ')}{shard.import_dependencies.length > 3 ? '...' : ''}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
