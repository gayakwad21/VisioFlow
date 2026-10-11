/**
 * VisioFlow Visual Node Graph Builder
 * Pure HTML5 / SVG / Vanilla JavaScript Engine
 */

class PipelineBuilder {
  constructor(canvasWrapperId, svgId) {
    this.container = document.getElementById(canvasWrapperId);
    this.svg = document.getElementById(svgId);
    this.nodes = [];
    this.edges = [];
    this.selectedNodeId = null;
    this.draggingNode = null;
    this.draggingChanged = false;
    this.dragOffset = { x: 0, y: 0 };
    this.connectingFrom = null;

    this.initEvents();
  }

  initEvents() {
    if (!this.container) return;

    this.container.addEventListener('mousemove', (e) => this.onMouseMove(e));
    this.container.addEventListener('mouseup', (e) => this.onMouseUp(e));

    this.container.addEventListener('dragover', (e) => e.preventDefault());
    this.container.addEventListener('drop', (e) => this.onDrop(e));
  }

  addNode(type, position = { x: 100, y: 100 }, data = {}) {
    const id = `node_${Date.now()}_${Math.floor(Math.random()*1000)}`;
    const node = { id, type, position, data };
    this.nodes.push(node);
    this.renderNode(node);
    this.selectNode(id);
    this.renderConnections();
    this.notifyGraphChanged();
    return node;
  }

  getNodeDefinition(type) {
    const defs = {
      imageSource: { name: 'Image Source', icon: '🖼️', defaultData: {} },
      output: { name: 'Output', icon: '📤', defaultData: {} },
      grayscale: { name: 'Grayscale', icon: '🎨', defaultData: {} },
      blur: { name: 'Blur', icon: '💧', defaultData: { strength: 5, blurType: 'gaussian' } },
      gaussianBlur: { name: 'Gaussian Blur', icon: '🌫️', defaultData: { kernelSize: 5, sigma: 0 } },
      medianBlur: { name: 'Median Blur', icon: '🧽', defaultData: { kernelSize: 5 } },
      canny: { name: 'Canny Edge', icon: '⚡', defaultData: { threshold1: 75, threshold2: 200 } },
      threshold: { name: 'Threshold', icon: '🌓', defaultData: { threshold: 127, mode: 'binary' } },
      adaptiveThreshold: { name: 'Adaptive Threshold', icon: '◐', defaultData: { blockSize: 11, constant: 2 } },
      morphological: { name: 'Morphology', icon: '🧪', defaultData: { operation: 'erode', iterations: 1 } },
      findContours: { name: 'Find Contours', icon: '📐', defaultData: { fill: false } },
      rotate: { name: 'Rotate', icon: '🔄', defaultData: { angle: 90 } },
      resize: { name: 'Resize', icon: '↔️', defaultData: { width: 640, height: 480 } },
      crop: { name: 'Crop', icon: '✂️', defaultData: { x: 0, y: 0, width: 320, height: 240 } },
      brightness: { name: 'Brightness', icon: '☀️', defaultData: { brightness: 20, contrast: 1.2 } },
      sharpen: { name: 'Sharpen', icon: '✳️', defaultData: { amount: 1 } },
      histogram: { name: 'Histogram', icon: '▥', defaultData: {} },
      imageStatistics: { name: 'Image Statistics', icon: '∑', defaultData: {} },
      objectDetection: { name: 'Object Detection', icon: '🔍', defaultData: { confidence: 0.5 } }
    };
    return defs[type] || { name: type, icon: '📦', defaultData: {} };
  }

  renderNode(node) {
    const def = this.getNodeDefinition(node.type);
    const div = document.createElement('div');
    div.className = 'editor-node';
    div.id = node.id;
    div.style.left = `${node.position.x}px`;
    div.style.top = `${node.position.y}px`;

    div.innerHTML = `
      <div class="node-header">
        <span>${def.icon} ${def.name}</span>
        <span class="node-delete" onclick="builder.deleteNode('${node.id}')">&times;</span>
      </div>
      <div class="node-body">
        <div class="node-id">ID: ${node.id.substring(0, 10)}</div>
      </div>
      <div class="port port-input" data-node="${node.id}" data-type="input"></div>
      <div class="port port-output" data-node="${node.id}" data-type="output"></div>
    `;

    div.addEventListener('mousedown', (e) => {
      if (e.target.classList.contains('port')) return;
      this.selectedNodeId = node.id;
      this.highlightSelectedNode();
      this.draggingNode = node;
      const rect = div.getBoundingClientRect();
      this.dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      if (window.onNodeSelected) window.onNodeSelected(node);
    });

    // Port connection handlers
    const outPort = div.querySelector('.port-output');
    outPort.addEventListener('mousedown', (e) => {
      e.stopPropagation();
      this.connectingFrom = node.id;
    });

    const inPort = div.querySelector('.port-input');
    inPort.addEventListener('mouseup', (e) => {
      e.stopPropagation();
      if (this.connectingFrom && this.connectingFrom !== node.id) {
        this.addConnection(this.connectingFrom, node.id);
        this.connectingFrom = null;
      }
    });

    this.container.appendChild(div);
  }

  addConnection(sourceId, targetId) {
    if (this.edges.some(e => e.source === sourceId && e.target === targetId)) return;
    this.edges.push({ id: `edge_${Date.now()}`, source: sourceId, target: targetId });
    this.renderConnections();
    this.notifyGraphChanged();
  }

  deleteNode(id) {
    this.nodes = this.nodes.filter(n => n.id !== id);
    this.edges = this.edges.filter(e => e.source !== id && e.target !== id);
    const elem = document.getElementById(id);
    if (elem) elem.remove();
    this.renderConnections();
    this.notifyGraphChanged();
    if (this.selectedNodeId === id) {
      this.selectedNodeId = null;
      if (window.onNodeSelected) window.onNodeSelected(null);
    }
  }

  highlightSelectedNode() {
    document.querySelectorAll('.editor-node').forEach(el => {
      if (el.id === this.selectedNodeId) {
        el.classList.add('selected');
      } else {
        el.classList.remove('selected');
      }
    });
  }

  selectNode(id) {
    this.selectedNodeId = id;
    this.highlightSelectedNode();
    const node = this.nodes.find(n => n.id === id);
    if (window.onNodeSelected) window.onNodeSelected(node);
  }

  onMouseMove(e) {
    if (this.draggingNode) {
      this.draggingChanged = true;
      const cRect = this.container.getBoundingClientRect();
      const x = e.clientX - cRect.left - this.dragOffset.x;
      const y = e.clientY - cRect.top - this.dragOffset.y;
      this.draggingNode.position = { x: Math.max(0, x), y: Math.max(0, y) };
      const elem = document.getElementById(this.draggingNode.id);
      if (elem) {
        elem.style.left = `${this.draggingNode.position.x}px`;
        elem.style.top = `${this.draggingNode.position.y}px`;
      }
      this.renderConnections();
    }
  }

  onMouseUp(e) {
    if (this.draggingChanged) this.notifyGraphChanged();
    this.draggingNode = null;
    this.draggingChanged = false;
    this.connectingFrom = null;
  }

  notifyGraphChanged() {
    this.container.dispatchEvent(new Event('graphchange'));
  }

  onDrop(e) {
    e.preventDefault();
    const type = e.dataTransfer.getData('node-type');
    if (!type) return;

    const cRect = this.container.getBoundingClientRect();
    const position = {
      x: e.clientX - cRect.left - 90,
      y: e.clientY - cRect.top - 25
    };
    const def = this.getNodeDefinition(type);
    this.addNode(type, position, { ...def.defaultData });
  }

  renderConnections() {
    if (!this.svg) return;
    this.svg.innerHTML = '';
    const cRect = this.container.getBoundingClientRect();

    this.edges.forEach(edge => {
      const srcNode = this.nodes.find(n => n.id === edge.source);
      const tgtNode = this.nodes.find(n => n.id === edge.target);
      if (!srcNode || !tgtNode) return;

      const srcX = srcNode.position.x + 180;
      const srcY = srcNode.position.y + 30;
      const tgtX = tgtNode.position.x;
      const tgtY = tgtNode.position.y + 30;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const dx = Math.abs(tgtX - srcX) * 0.5;
      const d = `M ${srcX} ${srcY} C ${srcX + dx} ${srcY}, ${tgtX - dx} ${tgtY}, ${tgtX} ${tgtY}`;

      path.setAttribute('d', d);
      path.setAttribute('stroke', '#f97316');
      path.setAttribute('stroke-width', '3');
      path.setAttribute('fill', 'none');
      this.svg.appendChild(path);
    });
  }

  loadGraph(graphData) {
    this.container.querySelectorAll('.editor-node').forEach(n => n.remove());
    this.nodes = [];
    this.edges = [];

    if (!graphData || !graphData.nodes) return;

    graphData.nodes.forEach(n => {
      const node = { id: n.id, type: n.type, position: n.position, data: n.data || {} };
      this.nodes.push(node);
      this.renderNode(node);
    });

    if (graphData.edges) {
      this.edges = graphData.edges.map(e => ({ ...e }));
    }
    this.renderConnections();
  }

  getGraphData() {
    return {
      nodes: this.nodes.map(n => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
      edges: this.edges.map(e => ({ id: e.id, source: e.source, target: e.target }))
    };
  }
}
