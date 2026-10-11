import React, { memo, useCallback, useMemo } from 'react'
import { ExpandableNode } from '@/nodes/base'
import { useNodeInput, useNodeOutput, DataTypes, createImagePayload } from '@/data'
import { useImageProcessor } from '@/hooks/useImageProcessor'
import { useNodeConfig } from '@/hooks/useNodeConfig'
import { processMorphology } from '@/services/imageProcessor'
import { Slider } from '@/components/ui/slider'
import { Select } from '@/components/ui/select'

/**
 * MorphologicalNode - Applies Morphological transformations (Erosion/Dilation)
 * Uses OpenCV.js (required, no fallback)
 */
function MorphologicalNode({ id, data, selected }) {
    const { data: inputData, isConnected } = useNodeInput(id, 'image-in', DataTypes.IMAGE)
    const inputImageUrl = inputData?.imageUrl
    const updateOutput = useNodeOutput(id)

    // Config synced to node.data for export
    const [config, setConfig] = useNodeConfig(id, {
        operation: data.operation ?? 'erode',
        iterations: data.iterations ?? 1,
    })
    const { operation, iterations } = config

    const handleOperationChange = useCallback((value) => {
        setConfig({ operation: value })
    }, [setConfig])

    const handleIterationsChange = useCallback((value) => {
        setConfig({ iterations: value })
    }, [setConfig])

    const processingOptions = useMemo(() => ({
        operation,
        iterations,
        metadata: inputData?.metadata
    }), [operation, iterations, inputData])

    const handleProcessingComplete = useCallback((result) => {
        updateOutput({
            image: createImagePayload({
                imageUrl: result.outputUrl,
                metadata: result.metadata,
            })
        })
    }, [updateOutput])

    const { isProcessing, error, isWaitingForOpenCV } = useImageProcessor(
        processMorphology,
        inputImageUrl,
        processingOptions,
        handleProcessingComplete,
        [operation, iterations]
    )

    const optionsContent = (
        <div className="space-y-4">
            <Select label="Operation" value={operation} onChange={handleOperationChange} options={[
                { value: 'erode', label: 'Erode' }, { value: 'dilate', label: 'Dilate' },
                { value: 'open', label: 'Open' }, { value: 'close', label: 'Close' },
            ]} />

            <Slider
                label="Iterations"
                value={iterations}
                onChange={handleIterationsChange}
                min={1}
                max={10}
                step={1}
                showValue
            />
        </div>
    )

    return (
        <ExpandableNode
            id={id}
            title="Morphology"
            inputs={[{ id: 'image-in' }]}
            outputs={[{ id: 'image-out' }]}
            selected={selected}
            image={data.image}
            isProcessing={isProcessing}
            isWaitingForOpenCV={isWaitingForOpenCV}
            error={error}
            isConnected={isConnected}
            options={optionsContent}
            className="w-[240px]"
        />
    )
}

export default memo(MorphologicalNode)
