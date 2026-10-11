import React, { useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'

export default function TemplateConfirmModal({ template, onCancel, onConfirm }) {
    useEffect(() => {
        const handleKeyDown = (event) => {
            if (event.key === 'Escape') onCancel()
        }
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [onCancel])

    if (!template) return null

    return <div className="template-confirm-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel() }}>
        <section className="template-confirm" role="dialog" aria-modal="true" aria-labelledby="template-confirm-title">
            <button className="icon-button template-confirm__close" onClick={onCancel} aria-label="Cancel template loading" title="Cancel"><X /></button>
            <div className="template-confirm__icon"><AlertTriangle /></div>
            <p className="eyebrow">Replace canvas</p>
            <h2 id="template-confirm-title">Load this template?</h2>
            <p>Your current canvas will be replaced with <strong>{template.name}</strong>.</p>
            <div className="template-confirm__actions"><button className="secondary-action" onClick={onCancel}>Cancel</button><button className="primary-action" onClick={onConfirm}>Load Template</button></div>
        </section>
    </div>
}