import { useState, useCallback, useEffect } from 'react'
import { useReactFlow } from 'reactflow'

/**
 * Manages node configuration state while keeping node.data in sync.
 * This allows getNodes() to always return the latest config values,
 * which is needed for features like code export.
 *
 * @param {string} nodeId - The ReactFlow node id
 * @param {object} defaultConfig - Initial config values (read from node data)
 * @returns {[object, function]} - [config, setConfig]
 */
export function useNodeConfig(nodeId, defaultConfig) {
    const { setNodes } = useReactFlow()
    const [config, setConfigState] = useState(defaultConfig)

    useEffect(() => {
        setConfigState((current) => {
            const changed = Object.keys(defaultConfig).some((key) => current[key] !== defaultConfig[key])
            return changed ? defaultConfig : current
        })
    }, [defaultConfig])

    const setConfig = useCallback((updater) => {
        setConfigState(prev => {
            const next = typeof updater === 'function'
                ? updater(prev)
                : { ...prev, ...updater }

            // Sync to node.data so getNodes() reflects current config
            setNodes(nodes => nodes.map(n =>
                n.id === nodeId ? { ...n, data: { ...n.data, ...next } } : n
            ))

            return next
        })
    }, [nodeId, setNodes])

    return [config, setConfig]
}
