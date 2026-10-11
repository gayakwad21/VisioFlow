import React from 'react'
import { ArrowUpRight, Sparkles } from 'lucide-react'
import { workflowPresets } from '@/data/workflows'

export default function WorkflowPresets({ selectedId, onSelect, mode }) {
    const visiblePresets = workflowPresets.filter((preset) => mode === 'computer-vision' || preset.mode === mode || preset.mode === 'architecture')
    return <section className="preset-panel">
        <div className="preset-panel__heading"><span><Sparkles className="h-4 w-4" /> Quick starts</span><span className="preset-panel__count">{visiblePresets.length}</span></div>
        <div className="preset-list">{visiblePresets.map((preset) => <button key={preset.id} className={`preset-item ${selectedId === preset.id ? 'is-selected' : ''}`} onClick={() => onSelect(preset)}><span><strong>{preset.name}</strong><small>{preset.description}</small></span><ArrowUpRight className="h-4 w-4 shrink-0" /></button>)}</div>
    </section>
}