import React, { useState } from 'react'
import { ChevronDown, Info } from 'lucide-react'

export default function WorkflowInfoPanel({ workflow }) {
    const [open, setOpen] = useState(true)
    if (!workflow) return null
    return <aside className={`workflow-info ${open ? 'is-open' : ''}`}><button className="workflow-info__toggle" onClick={() => setOpen(!open)} aria-expanded={open}><span><Info className="h-4 w-4" /> Workflow brief</span><ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} /></button>{open && <div className="workflow-info__body"><p className="eyebrow">Selected workflow</p><h2>{workflow.name}</h2><p>{workflow.description}</p><ol>{workflow.steps.map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, '0')}</span>{step}</li>)}</ol></div>}</aside>
}