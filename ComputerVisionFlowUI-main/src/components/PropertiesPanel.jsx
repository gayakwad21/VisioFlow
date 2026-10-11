import React from 'react'
import { SlidersHorizontal, X } from 'lucide-react'

const definitions = {
    blur: { name: 'Blur', fields: [{ key: 'strength', label: 'Strength', min: 1, max: 50, step: 1 }] },
    brightness: { name: 'Brightness', fields: [{ key: 'brightness', label: 'Brightness', min: -100, max: 100, step: 1 }, { key: 'contrast', label: 'Contrast', min: 0, max: 3, step: .01 }] },
    canny: { name: 'Canny Edge', fields: [{ key: 'threshold1', label: 'Low Threshold', min: 0, max: 500, step: 1 }, { key: 'threshold2', label: 'High Threshold', min: 0, max: 500, step: 1 }] },
    rotate: { name: 'Rotate', fields: [{ key: 'angle', label: 'Angle', min: -180, max: 180, step: 1 }] },
    morphological: { name: 'Morphology', fields: [{ key: 'operation', label: 'Operation', type: 'select', options: [{ value: 'erode', label: 'Erode' }, { value: 'dilate', label: 'Dilate' }, { value: 'open', label: 'Open' }, { value: 'close', label: 'Close' }] }, { key: 'iterations', label: 'Iterations', min: 1, max: 20, step: 1 }] },
    threshold: { name: 'Threshold', fields: [{ key: 'threshold', label: 'Threshold value', min: 0, max: 255, step: 1 }, { key: 'mode', label: 'Mode', type: 'select', options: [{ value: 'select', label: 'Keep selection' }, { value: 'filter', label: 'Reject selection' }] }] },
}

export default function PropertiesPanel({ isOpen, node, onClose, onUpdate }) {
    const definition = node && definitions[node.type]
    return <aside className={`properties-panel ${isOpen ? 'is-open' : ''}`} aria-hidden={!isOpen}>
        <div className="properties-heading"><span><SlidersHorizontal /> INSPECTOR</span><button className="icon-button" onClick={onClose} title="Close inspector" aria-label="Close Inspector"><X /></button></div>
        {!node ? <div className="inspector-empty"><SlidersHorizontal /><strong>Properties</strong><p>Select a node to view and edit its properties.</p></div> : <div className="inspector-content"><p className="inspector-kicker">Node details</p><h2>{definition?.name || node.type}</h2><p className="node-type">{node.type} node · {node.id}</p><div className="inspector-divider" /><p className="inspector-kicker">Parameters</p>{definition?.fields.length ? definition.fields.map((field) => { const rawValue = field.key === 'threshold' ? node.data.ranges?.[0]?.[1] ?? 255 : node.data[field.key]; const value = rawValue ?? (field.key === 'contrast' ? 1 : field.type === 'select' ? field.options[0].value : 0); return <label className="inspector-field" key={field.key}><span><b>{field.label}</b>{field.type !== 'select' && <input className="inspector-number" type="number" min={field.min} max={field.max} step={field.step} value={value} onChange={(event) => onUpdate(field.key, Number(event.target.value))} />}</span>{field.type === 'select' ? <select value={value} onChange={(event) => onUpdate(field.key, event.target.value)}>{field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input type="range" min={field.min} max={field.max} step={field.step} value={value} onChange={(event) => onUpdate(field.key, Number(event.target.value))} />}</label> }) : <p className="inspector-note">This node has no adjustable parameters. Connect it to an image source to process the workflow.</p>}</div>}
    </aside>
}