import React from 'react'
import { Activity, Circle, GitBranch } from 'lucide-react'

export default function StatusBar({ nodeCount, edgeCount, zoom }) {
    return <footer className="status-bar"><span className="status-online"><Circle /> OpenCV Ready</span><span><GitBranch /> {nodeCount} nodes</span><span>{edgeCount} connections</span><span className="status-zoom">Zoom {Math.round(zoom * 100)}%</span><span className="status-right"><Activity /> Pipeline ready</span></footer>
}