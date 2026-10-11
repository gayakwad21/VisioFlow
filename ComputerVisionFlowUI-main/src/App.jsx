import React, { useCallback, useEffect, useRef, useState } from 'react'
import ReactFlow, {
    Controls,
    Background,
    Panel,
    addEdge,
    ReactFlowProvider,
    useEdges,
    useNodes,
    useViewport,
    useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { OpenCVProvider } from '@/contexts/OpenCVContext'
import { nodeTypes } from '@/nodes'
import AddNodeMenu from '@/components/AddNodeMenu'
import OpenCVStatus from '@/components/OpenCVStatus'
import ExportModal from '@/components/ExportModal'
import WorkspaceModeSelector from '@/components/WorkspaceModeSelector'
import WorkflowInfoPanel from '@/components/WorkflowInfoPanel'
import EmptyCanvasWelcome from '@/components/EmptyCanvasWelcome'
import Sidebar from '@/components/Sidebar'
import PropertiesPanel from '@/components/PropertiesPanel'
import StatusBar from '@/components/StatusBar'
import WorkspacePanel from '@/components/WorkspacePanel'
import TemplateConfirmModal from '@/components/TemplateConfirmModal'
import { createPresetWorkflow } from '@/data/workflows'
import elephantImg from '../asset/imagenet_elephant.jpg'

function readStoredWorkflows() {
    try {
        const stored = localStorage.getItem('visionforge-workflows')
        if (!stored) return []
        const parsed = JSON.parse(stored)
        if (!Array.isArray(parsed)) return []
        return parsed.filter((workflow) => workflow && typeof workflow === 'object' && Array.isArray(workflow.nodes) && Array.isArray(workflow.edges))
    } catch (error) {
        console.warn('[VisioFlow] Ignoring invalid saved workflows.', error)
        return []
    }
}

function readStoredTheme() {
    try {
        const stored = localStorage.getItem('visionforge-theme')
        if (stored === 'dark' || stored === 'light') return stored
    } catch (error) {
        console.warn('[VisioFlow] Theme preference is unavailable.', error)
    }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

// Helper to add some visual noise to node positions
const jitter = (val, range = 20) => val + (Math.random() - 0.5) * range

// Initial nodes for the visualization pipeline
const initialNodes = [
    {
        id: 'source-1',
        type: 'imageSource',
        position: { x: jitter(50), y: jitter(300, 150) },
        data: { imageUrl: elephantImg, imageName: 'imagenet_elephant.jpg' },
    },
    // Pipeline 1: Grayscale -> Blur -> Threshold -> Find Contours -> Erode -> Dilate
    {
        id: 'grayscale-1',
        type: 'grayscale',
        position: { x: jitter(400), y: jitter(100, 150) },
        data: {},
    },
    {
        id: 'blur-1',
        type: 'blur',
        position: { x: jitter(700), y: jitter(100, 150) },
        data: { strength: 5 },
    },
    {
        id: 'thresh-1',
        type: 'threshold',
        position: { x: jitter(1000), y: jitter(100, 150) },
        data: {
            // Reject 140-255 (Keep 0-139)
            mode: 'filter',
            ranges: [[140, 255]]
        },
    },
    {
        id: 'contours-1',
        type: 'findContours',
        position: { x: jitter(1300), y: jitter(100, 150) },
        data: { fill: true },
    },
    {
        id: 'erode-1',
        type: 'morphological',
        position: { x: jitter(1600), y: jitter(100, 150) },
        data: { operation: 'erode', iterations: 4 },
    },
    {
        id: 'dilate-1',
        type: 'morphological',
        position: { x: jitter(1900), y: jitter(100, 150) },
        data: { operation: 'dilate', iterations: 4 },
    },
    // Pipeline 2: Threshold (RGB) -> Find Contours
    {
        id: 'thresh-2',
        type: 'threshold',
        position: { x: jitter(400), y: jitter(500, 150) },
        data: {
            // Keep roughly middle values
            mode: 'select',
            ranges: [[50, 200], [50, 200], [50, 200]]
        },
    },
    {
        id: 'contours-2',
        type: 'findContours',
        position: { x: jitter(750), y: jitter(500, 150) },
        data: { fill: false },
    },
    // Pipeline 3: Brightness -> Invert -> Rotate -> Canny
    {
        id: 'brightness-1',
        type: 'brightness',
        position: { x: jitter(400), y: jitter(900, 150) },
        data: { brightness: 20, contrast: 1.2 },
    },
    {
        id: 'invert-1',
        type: 'invert',
        position: { x: jitter(700), y: jitter(900, 150) },
        data: {},
    },
    {
        id: 'rotate-1',
        type: 'rotate',
        position: { x: jitter(1000), y: jitter(900, 150) },
        data: { angle: 15 },
    },
    {
        id: 'canny-1',
        type: 'canny',
        position: { x: jitter(1300), y: jitter(900, 150) },
        data: { threshold1: 75, threshold2: 200 },
    },
]

const initialEdges = [
    // Pipeline 1 Connections
    { id: 'e1-1', source: 'source-1', sourceHandle: 'image-out', target: 'grayscale-1', targetHandle: 'image-in', animated: true },
    { id: 'e1-2', source: 'grayscale-1', sourceHandle: 'image-out', target: 'blur-1', targetHandle: 'image-in', animated: true },
    { id: 'e1-3', source: 'blur-1', sourceHandle: 'image-out', target: 'thresh-1', targetHandle: 'image-in', animated: true },
    { id: 'e1-4', source: 'thresh-1', sourceHandle: 'image-out', target: 'contours-1', targetHandle: 'image-in', animated: true },
    { id: 'e1-5', source: 'contours-1', sourceHandle: 'image-out', target: 'erode-1', targetHandle: 'image-in', animated: true },
    { id: 'e1-6', source: 'erode-1', sourceHandle: 'image-out', target: 'dilate-1', targetHandle: 'image-in', animated: true },

    // Pipeline 2 Connections
    { id: 'e2-1', source: 'source-1', sourceHandle: 'image-out', target: 'thresh-2', targetHandle: 'image-in', animated: true },
    { id: 'e2-2', source: 'thresh-2', sourceHandle: 'image-out', target: 'contours-2', targetHandle: 'image-in', animated: true },

    // Pipeline 3 Connections
    { id: 'e3-1', source: 'source-1', sourceHandle: 'image-out', target: 'brightness-1', targetHandle: 'image-in', animated: true },
    { id: 'e3-2', source: 'brightness-1', sourceHandle: 'image-out', target: 'invert-1', targetHandle: 'image-in', animated: true },
    { id: 'e3-3', source: 'invert-1', sourceHandle: 'image-out', target: 'rotate-1', targetHandle: 'image-in', animated: true },
    { id: 'e3-4', source: 'rotate-1', sourceHandle: 'image-out', target: 'canny-1', targetHandle: 'image-in', animated: true },
]

function FlowCanvas({ mode, projectName, onProjectChange, selectedPreset, onPresetChange }) {
    const nodeIdCounter = useRef(2)
    const { getViewport, addNodes, setEdges, setNodes, getNodes, getEdges, fitView } = useReactFlow()
    const nodes = useNodes()
    const edges = useEdges()
    const viewport = useViewport()
    const [showExport, setShowExport] = useState(false)
    const [hasNodes, setHasNodes] = useState(true)
    const [selectedNodeId, setSelectedNodeId] = useState(null)
    const [isInspectorOpen, setIsInspectorOpen] = useState(true)
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
    const [showWorkspace, setShowWorkspace] = useState(false)
    const [pendingTemplate, setPendingTemplate] = useState(null)
    const [templateError, setTemplateError] = useState('')
    const [savedWorkflows, setSavedWorkflows] = useState(readStoredWorkflows)
    const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null

    useEffect(() => {
        setHasNodes(nodes.length > 0)
    }, [nodes.length])

    // Key fix: Use defaultNodes/defaultEdges for uncontrolled mode
    // allowing nodes to update themselves via useNodeOutput without fighting App state

    const onConnect = useCallback(
        (params) => {
            setEdges((eds) => {
                // Enforce one connection per input handle
                const filteredEdges = eds.filter(
                    (edge) =>
                        !(
                            edge.target === params.target &&
                            edge.targetHandle === params.targetHandle
                        )
                )
                return addEdge({ ...params, animated: true }, filteredEdges)
            })
        },
        [setEdges]
    )

    const handleAddNode = useCallback((nodeType) => {
        nodeIdCounter.current += 1
        const id = `${nodeType}-${nodeIdCounter.current}`

        const viewport = getViewport()
        const position = {
            x: (-viewport.x + 300 + Math.random() * 200) / viewport.zoom,
            y: (-viewport.y + 200 + Math.random() * 100) / viewport.zoom,
        }

        const newNode = {
            id,
            type: nodeType,
            position,
            data: {},
        }

        addNodes(newNode)
        setHasNodes(true)
    }, [getViewport, addNodes])

    const handleClearCanvas = useCallback(() => {
        const confirmed = window.confirm(
            'Clear the canvas and remove all nodes and connections?'
        )
        if (!confirmed) return
        setNodes([])
        setEdges([])
        nodeIdCounter.current = 0
        setHasNodes(false)
    }, [setNodes, setEdges])

    const applyTemplate = useCallback((workflow) => {
        if (!workflow?.preset || !Array.isArray(workflow.nodes) || !Array.isArray(workflow.edges)) {
            setTemplateError('This template is unavailable. Choose another workflow.')
            return
        }
        const nodeIds = new Set(workflow.nodes.map((node) => node.id))
        const validEdges = workflow.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
        if (validEdges.length !== workflow.edges.length) {
            setTemplateError('This template contains an invalid connection and could not be loaded.')
            return
        }
        setNodes(workflow.nodes)
        setEdges(validEdges)
        nodeIdCounter.current = workflow.nodes.length + 1
        setHasNodes(true)
        setTemplateError('')
        onProjectChange(workflow.preset.name)
        onPresetChange(workflow.preset)
        setPendingTemplate(null)
        setTimeout(() => fitView({ padding: 0.2, duration: 500 }), 50)
    }, [fitView, onPresetChange, onProjectChange, setEdges, setNodes])

    const handleLoadTemplate = useCallback((template) => {
        const workflow = createPresetWorkflow(template?.id)
        if (!workflow) {
            setTemplateError('This template is unavailable. Choose another workflow.')
            return
        }
        if (nodes.length > 0) {
            setPendingTemplate(workflow)
            return
        }
        applyTemplate(workflow)
    }, [applyTemplate, nodes.length])

    const confirmTemplateLoad = useCallback(() => {
        if (pendingTemplate) applyTemplate(pendingTemplate)
    }, [applyTemplate, pendingTemplate])

    const startScratch = useCallback(() => {
        setNodes([])
        setEdges([])
        setHasNodes(false)
        onPresetChange(null)
        setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50)
    }, [fitView, onPresetChange, setEdges, setNodes])

    const updateSelectedNode = useCallback((key, value) => {
        if (!selectedNode) return
        setNodes((currentNodes) => currentNodes.map((node) => {
            if (node.id !== selectedNode.id) return node
            const data = key === 'threshold' ? { ...node.data, ranges: [[0, value]] } : { ...node.data, [key]: value }
            return { ...node, data }
        }))
    }, [selectedNode, setNodes])

    const handleNewWorkflow = useCallback(() => {
        setNodes([])
        setEdges([])
        setHasNodes(false)
        setSelectedNodeId(null)
        onPresetChange(null)
    }, [onPresetChange, setEdges, setNodes])

    const saveWorkflow = useCallback(() => {
        const now = new Date().toISOString()
        const existing = savedWorkflows.find((workflow) => workflow.projectName === projectName)
        const workflow = { id: existing?.id || `workflow-${Date.now()}`, projectName, mode, nodes: getNodes(), edges: getEdges(), createdAt: existing?.createdAt || now, updatedAt: now }
        const next = [workflow, ...savedWorkflows.filter((item) => item.id !== workflow.id)]
        setSavedWorkflows(next)
        localStorage.setItem('visionforge-workflows', JSON.stringify(next))
    }, [getEdges, getNodes, mode, projectName, savedWorkflows])

    const loadWorkflow = useCallback((workflow) => {
        setNodes(workflow.nodes)
        setEdges(workflow.edges)
        setHasNodes(workflow.nodes.length > 0)
        nodeIdCounter.current = workflow.nodes.length + 1
        onProjectChange(workflow.projectName)
        onPresetChange(null)
        setTimeout(() => fitView({ padding: 0.2, duration: 500 }), 50)
        setShowWorkspace(false)
    }, [fitView, onPresetChange, onProjectChange, setEdges, setNodes])

    const deleteWorkflow = useCallback((workflowId) => {
        const next = savedWorkflows.filter((workflow) => workflow.id !== workflowId)
        setSavedWorkflows(next)
        localStorage.setItem('visionforge-workflows', JSON.stringify(next))
    }, [savedWorkflows])

    return (
        <>
            <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} mode={mode} selectedPreset={selectedPreset} onPresetSelect={handleLoadTemplate} onNew={handleNewWorkflow} onWorkspace={() => setShowWorkspace(true)} />
            <ReactFlow
                defaultNodes={initialNodes}
                defaultEdges={initialEdges}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                className="visionforge-flow"
                onSelectionChange={(selection) => setSelectedNodeId(selection.nodes[0]?.id || null)}
                onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            >
                <Background variant="dots" gap={16} size={1} />
                <Controls />
                {!hasNodes && <EmptyCanvasWelcome onDemo={() => handleLoadTemplate({ id: 'cv-demo' })} onArchitecture={() => handleLoadTemplate({ id: 'building-edges' })} onScratch={startScratch} />}
                <AddNodeMenu
                    onAddNode={handleAddNode}
                    onExportCode={() => setShowExport(true)}
                    onSaveWorkflow={saveWorkflow}
                    onClearCanvas={handleClearCanvas}
                    isInspectorOpen={isInspectorOpen}
                    onToggleInspector={() => setIsInspectorOpen((open) => !open)}
                />
            </ReactFlow>

            <PropertiesPanel isOpen={isInspectorOpen} node={selectedNode} onClose={() => setIsInspectorOpen(false)} onUpdate={updateSelectedNode} />
            <StatusBar nodeCount={nodes.length} edgeCount={edges.length} zoom={viewport.zoom} />

            {showExport && (
                <ExportModal
                    nodes={getNodes()}
                    edges={getEdges()}
                    projectName={projectName}
                    workspaceMode={mode}
                    selectedPreset={selectedPreset?.name}
                    onClose={() => setShowExport(false)}
                />
            )}
            <WorkflowInfoPanel workflow={selectedPreset} />
            {showWorkspace && <WorkspacePanel workflows={savedWorkflows} onLoad={loadWorkflow} onDelete={deleteWorkflow} onClose={() => setShowWorkspace(false)} />}
            {templateError && <div className="template-error" role="alert">{templateError}<button onClick={() => setTemplateError('')} aria-label="Dismiss template error">Dismiss</button></div>}
            <TemplateConfirmModal template={pendingTemplate?.preset} onCancel={() => setPendingTemplate(null)} onConfirm={confirmTemplateLoad} />
        </>
    )
}

function App() {
    const [mode, setMode] = useState('computer-vision')
    const [projectName, setProjectName] = useState('Untitled VisionForge Project')
    const [selectedPreset, setSelectedPreset] = useState(null)
    const [theme, setTheme] = useState(readStoredTheme)

    useEffect(() => {
        document.documentElement.dataset.theme = theme
        localStorage.setItem('visionforge-theme', theme)
    }, [theme])

    const handlePresetChange = useCallback((preset) => {
        setSelectedPreset(preset)
        if (preset) setMode(preset.mode)
    }, [])

    return (
        <OpenCVProvider>
            <div className="visionforge-app w-screen h-screen">
                <header className="app-header">
                    <div className="brand-lockup">
                        <div className="brand-kicker">VF / STUDIO <span>BUILD • ANALYZE • TRANSFORM</span></div>
                        <h1>VisionForge</h1>
                        <p>Visual Intelligence &amp; Image Analysis Studio</p>
                    </div>
                    <div className="header-controls">
                        <input aria-label="Workflow name" value={projectName} onChange={(event) => setProjectName(event.target.value)} />
                        <WorkspaceModeSelector value={mode} onChange={(value) => { setMode(value); setSelectedPreset(null) }} />
                        <button className="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>{theme === 'dark' ? 'LIGHT' : 'DARK'}</button>
                        <OpenCVStatus />
                    </div>
                </header>
                <ReactFlowProvider>
                    <FlowCanvas mode={mode} projectName={projectName} onProjectChange={setProjectName} selectedPreset={selectedPreset} onPresetChange={handlePresetChange} />
                </ReactFlowProvider>
            </div>
        </OpenCVProvider>
    )
}

export default App
