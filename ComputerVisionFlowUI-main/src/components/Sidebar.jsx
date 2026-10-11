import React from 'react'
import { Boxes, FilePlus2, FolderOpen, LayoutTemplate, PanelLeftClose, PanelLeftOpen, Workflow } from 'lucide-react'
import WorkflowPresets from '@/components/WorkflowPresets'

export default function Sidebar({ collapsed, onToggle, mode, selectedPreset, onPresetSelect, onNew, onWorkspace }) {
    return <aside className={`app-sidebar ${collapsed ? 'is-collapsed' : ''}`}>
        <div className="sidebar-top"><div className="sidebar-title"><div className="sidebar-logo">VF</div>{!collapsed && <span>WORKSPACE</span>}</div><button className="icon-button" onClick={onToggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}</button></div>
        {!collapsed && <>
            <nav className="sidebar-nav">
                <button onClick={onNew}><FilePlus2 /> New Workflow</button>
                <button onClick={onWorkspace}><FolderOpen /> My Workflows</button>
                <button><LayoutTemplate /> Templates</button>
            </nav>
            <div className="sidebar-section-label"><Boxes /> QUICK START</div>
            <WorkflowPresets mode={mode} selectedId={selectedPreset?.id} onSelect={onPresetSelect} />
        </>}
        {collapsed && <div className="sidebar-collapsed-mark"><Workflow /></div>}
    </aside>
}