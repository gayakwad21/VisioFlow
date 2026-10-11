import React from 'react'
import { ArrowRight, Boxes, Sparkles } from 'lucide-react'

export default function EmptyCanvasWelcome({ onDemo, onArchitecture, onScratch }) {
    return <div className="empty-welcome"><div className="empty-welcome__mark"><Sparkles className="h-5 w-5" /></div><p className="eyebrow">VisionForge workspace</p><h2>Build visual intelligence workflows.</h2><p>Compose practical image-processing pipelines without writing complex computer vision code.</p><div className="empty-welcome__actions"><button className="primary-action" onClick={onDemo}>Computer Vision Demo <ArrowRight className="h-4 w-4" /></button><button className="secondary-action" onClick={onArchitecture}><Boxes className="h-4 w-4" /> Architecture Presets</button><button className="text-action" onClick={onScratch}>Start from Scratch</button></div></div>
}