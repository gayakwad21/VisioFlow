import elephantImg from '../../asset/imagenet_elephant.jpg'

export const workspaceModes = [
    { id: 'computer-vision', label: 'Computer Vision', description: 'Explore practical image-processing pipelines.' },
    { id: 'architecture', label: 'Architecture Analysis', description: 'Reveal structure, edges, and boundaries in built environments.' },
    { id: 'interior', label: 'Interior Analysis', description: 'Study visual boundaries and spatial features.' },
    { id: 'shapes', label: 'Object & Shape Analysis', description: 'Trace contours and transform visual forms.' },
]

const stepLabels = ['Image Input', 'Image Preprocessing', 'Image Enhancement', 'Edge / Shape Detection', 'Contour Analysis']

const nodeDefaults = {
    imageSource: { imageUrl: elephantImg, imageName: 'imagenet_elephant.jpg' },
    grayscale: {}, blur: { strength: 5 }, threshold: { mode: 'filter', ranges: [[140, 255]] },
    morphological: { operation: 'erode', iterations: 2 }, findContours: { fill: true },
    brightness: { brightness: 20, contrast: 1.2 }, colorConvert: {}, canny: { threshold1: 75, threshold2: 200 },
}

const presetDefinitions = [
    { id: 'edge-detection', name: 'Edge Detection', category: 'Computer Vision', mode: 'computer-vision', description: 'Convert, smooth, and trace image edges with the implemented OpenCV pipeline.', types: ['imageSource', 'grayscale', 'blur', 'canny'] },
    { id: 'contour-detection', name: 'Contour Detection', category: 'Computer Vision', mode: 'shapes', description: 'Segment an image, extract contours, and refine the result with morphology.', types: ['imageSource', 'grayscale', 'threshold', 'findContours', 'morphological'] },
    { id: 'image-enhancement', name: 'Image Enhancement', category: 'Computer Vision', mode: 'computer-vision', description: 'Adjust brightness and contrast, then apply a real blur filter for preprocessing.', types: ['imageSource', 'brightness', 'blur'] },
    { id: 'cv-demo', name: 'Computer Vision Demo', category: 'Computer Vision', mode: 'computer-vision', description: 'A complete introductory pipeline for preprocessing, segmentation, and shape extraction.', types: ['imageSource', 'grayscale', 'blur', 'threshold', 'findContours', 'morphological'] },
    { id: 'building-edges', name: 'Building Edge Analysis', category: 'Architecture', mode: 'architecture', description: 'Highlight structural edges and boundaries in building images.', types: ['imageSource', 'grayscale', 'blur', 'canny', 'findContours'] },
    { id: 'floor-plan', name: 'Floor Plan Analysis', category: 'Architecture', mode: 'architecture', description: 'Use thresholding and morphology to visualize walls, room boundaries, and structural shapes.', types: ['imageSource', 'grayscale', 'threshold', 'morphological', 'findContours'] },
    { id: 'facade', name: 'Facade Analysis', category: 'Architecture', mode: 'architecture', description: 'Highlight architectural lines and shapes with the available edge and contour processors.', types: ['imageSource', 'grayscale', 'brightness', 'canny', 'findContours'] },
    { id: 'interior-space', name: 'Interior Space Analysis', category: 'Interior', mode: 'interior', description: 'Analyze visual boundaries and structural features in interior images.', types: ['imageSource', 'brightness', 'colorConvert', 'canny', 'findContours'] },
    { id: 'floor-plan-template', name: 'Architecture Floor Plan Analysis', category: 'Architecture', mode: 'architecture', description: 'Preprocess a scanned plan and reveal structural boundaries with thresholding, morphology, and contours.', types: ['imageSource', 'grayscale', 'threshold', 'morphological', 'findContours', 'canny'] },
    { id: 'drone-analysis', name: 'Drone Image Analysis', category: 'Architecture', mode: 'architecture', description: 'Trace structural edges in an aerial image with smoothing, Canny detection, morphology, and contours.', types: ['imageSource', 'grayscale', 'blur', 'canny', 'morphological', 'findContours'] },
    { id: 'interior-analysis', name: 'Interior Analysis', category: 'Interior', mode: 'interior', description: 'Enhance an interior image and trace visual boundaries with the available edge and contour nodes.', types: ['imageSource', 'brightness', 'canny', 'findContours'] },
    { id: 'building-facade', name: 'Building Facade Analysis', category: 'Architecture', mode: 'architecture', description: 'Highlight architectural lines and shapes in building facades.', types: ['imageSource', 'grayscale', 'blur', 'canny', 'findContours'] },
]

function buildWorkflowGraph(preset) {
    const nodes = preset.types.map((type, index) => ({
        id: `${preset.id}-${type}-${index + 1}`,
        type,
        position: { x: 80 + index * 300, y: 220 + (index % 2) * 24 },
        data: { ...(nodeDefaults[type] || {}) },
    }))
    const edges = nodes.slice(1).map((node, index) => ({
        id: `${preset.id}-edge-${index + 1}`,
        source: nodes[index].id,
        sourceHandle: 'image-out',
        target: node.id,
        targetHandle: 'image-in',
        animated: true,
    }))
    return { nodes, edges }
}

export const workflowPresets = presetDefinitions.map((preset) => ({
    ...preset,
    steps: stepLabels,
    ...buildWorkflowGraph(preset),
}))

export function createPresetWorkflow(presetId) {
    const preset = workflowPresets.find((item) => item.id === presetId)
    if (!preset) return null
    return {
        preset,
        nodes: preset.nodes.map((node) => ({ ...node, position: { ...node.position }, data: { ...node.data } })),
        edges: preset.edges.map((edge) => ({ ...edge })),
    }
}