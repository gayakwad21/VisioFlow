import React from 'react'
import { Layers3 } from 'lucide-react'
import { workspaceModes } from '@/data/workflows'

export default function WorkspaceModeSelector({ value, onChange }) {
    return <label className="mode-selector"><span className="sr-only">Workspace mode</span><Layers3 className="h-4 w-4" /><select value={value} onChange={(event) => onChange(event.target.value)}>{workspaceModes.map((mode) => <option key={mode.id} value={mode.id}>{mode.label}</option>)}</select></label>
}