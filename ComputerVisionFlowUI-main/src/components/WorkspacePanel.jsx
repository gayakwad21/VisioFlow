import React from 'react'
import { Clock3, FolderOpen, Trash2, X } from 'lucide-react'

export default function WorkspacePanel({ workflows, onLoad, onDelete, onClose }) {
    return <div className="workspace-drawer">
        <div className="workspace-drawer__header"><span><FolderOpen /> My Workspace</span><button className="icon-button" onClick={onClose} title="Close workspace"><X /></button></div>
        <p className="workspace-drawer__hint">Saved workflows stay on this device.</p>
        {workflows.length === 0 ? <div className="workspace-empty"><FolderOpen /><p>No saved workflows yet.</p></div> : <div className="saved-workflows">{workflows.map((workflow) => <div className="saved-workflow" key={workflow.id}><button onClick={() => onLoad(workflow)}><strong>{workflow.projectName}</strong><small><Clock3 /> {new Date(workflow.updatedAt).toLocaleString()} · {workflow.nodes.length} nodes</small></button><button className="delete-saved" onClick={() => onDelete(workflow.id)} title="Delete saved workflow"><Trash2 /></button></div>)}</div>}
    </div>
}