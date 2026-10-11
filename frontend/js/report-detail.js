const reportId = new URLSearchParams(window.location.search).get('id');
let activeReport = null;
let activeJob = null;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function statusToken(value) {
  return String(value || 'not_available').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
}

function known(value) {
  return value !== null && value !== undefined && value !== '';
}

function valueLabel(value) {
  return known(value) ? String(value) : 'Not available';
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return 'Not available';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unit = -1;
  do {
    size /= 1024;
    unit += 1;
  } while (size >= 1024 && unit < units.length - 1);
  return `${size.toFixed(2)} ${units[unit]}`;
}

function formatDate(value) {
  if (!value) return 'Not available';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not available' : date.toLocaleString();
}

function formatDimension(width, height) {
  return known(width) && known(height) ? `${width} × ${height} px` : 'Not available';
}

function operationDescription(type) {
  const descriptions = {
    grayscale: 'Converts a colour image to grayscale.',
    blur: 'Reduces high-frequency detail and noise using the configured blur type.',
    gaussianBlur: 'Reduces high-frequency detail and noise with a Gaussian kernel.',
    medianBlur: 'Reduces impulse noise while preserving many edges.',
    canny: 'Highlights strong image edges; it does not identify vehicles, defects, or other objects.',
    threshold: 'Separates pixels using the configured intensity threshold.',
    adaptiveThreshold: 'Thresholds image regions using their local intensity.',
    morphological: 'Applies the configured erosion, dilation, opening, or closing operation.',
    rotate: 'Rotates the image by the configured angle.',
    resize: 'Resizes the image to the configured dimensions.',
    crop: 'Crops the image to the configured region.',
    brightness: 'Adjusts image brightness and contrast.',
    sharpen: 'Increases local edge contrast to sharpen the image.',
    findContours: 'Finds image contours; it does not classify objects.',
    histogram: 'Calculates image intensity distribution data.',
    imageStatistics: 'Calculates image statistics.',
    objectDetection: 'Runs the configured detection operation. Detection claims are limited to results recorded by the job.'
  };
  return descriptions[type] || 'Applied the recorded pipeline operation.';
}

function logsArray(job, content) {
  const logs = job?.result?.logs ?? content.logs ?? [];
  if (Array.isArray(logs)) return logs.map(log => typeof log === 'string' ? log : JSON.stringify(log));
  return known(logs) ? [String(logs)] : [];
}

function safeMediaUrl(rawUrl) {
  if (!rawUrl) return null;
  try {
    const url = new URL(rawUrl, window.location.origin);
    if (url.origin !== window.location.origin ||
        !/^\/api\/(?:files|jobs)\//.test(url.pathname)) return null;
    return url.href;
  } catch {
    return null;
  }
}

function renderPreview(element, url, type, alt) {
  const safeUrl = safeMediaUrl(url);
  if (!safeUrl) {
    element.innerHTML = '<span class="text-muted">Preview is not available.</span>';
    return;
  }
  const isVideo = String(type || '').toUpperCase() === 'VIDEO' || String(type || '').startsWith('video/');
  element.innerHTML = isVideo
    ? `<video controls preload="metadata"><source src="${escapeHtml(safeUrl)}" type="${escapeHtml(type || 'video/mp4')}">Video playback is not supported by this browser.</video>`
    : `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener"><img src="${escapeHtml(safeUrl)}" alt="${escapeHtml(alt)}"></a>`;
}

function definitionList(entries) {
  return entries.map(([label, value]) =>
    `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueLabel(value))}</dd></div>`
  ).join('');
}

function metricEntries(metrics) {
  return Object.entries(metrics || {}).filter(([, value]) => value !== null && value !== undefined);
}

function metricLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function operationSteps(content, job, logs) {
  const pipeline = content.pipeline || {};
  const graphNodes = job?.pipeline_graph?.nodes || pipeline.graph_data?.nodes || [];
  let steps = Array.isArray(pipeline.steps) ? pipeline.steps.slice() : [];
  if (!steps.length && Array.isArray(graphNodes)) {
    steps = graphNodes.map(node => ({
      node_id: node.id,
      type: node.type,
      name: node.data?.label || null,
      parameters: node.data || {},
      status: 'not_available'
    }));
  }

  const logSequence = [];
  const nodeEvent = /Node ['"]([^'"]+)['"]/i;
  logs.forEach((line, index) => {
    const match = line.match(nodeEvent);
    if (match && !logSequence.some(entry => entry.id === match[1])) {
      logSequence.push({ id: match[1], index });
    }
  });
  if (logSequence.length) {
    const sequenceIndex = new Map(logSequence.map(item => [item.id, item.index]));
    steps = steps.map((step, index) => ({ step, index })).sort((left, right) => {
      const leftIndex = sequenceIndex.get(left.step.node_id);
      const rightIndex = sequenceIndex.get(right.step.node_id);
      if (leftIndex === undefined && rightIndex === undefined) return left.index - right.index;
      if (leftIndex === undefined) return 1;
      if (rightIndex === undefined) return -1;
      return leftIndex - rightIndex;
    }).map(entry => entry.step);
  }

  return steps.map(step => {
    const nodeLogs = logs.filter(line => step.node_id && line.includes(`Node '${step.node_id}'`));
    let status = step.status || 'not_available';
    if (nodeLogs.some(line => /completed\.|initialized\./i.test(line))) status = 'success';
    else if (nodeLogs.some(line => /\b(failed|error)\b/i.test(line))) status = 'failed';
    return { ...step, status };
  });
}

function renderOperations(steps, result) {
  const entries = steps.filter(step => !['imageSource', 'output'].includes(step.type));
  const detectionResults = result?.detected_objects;
  const operationHtml = entries.map((step, index) => {
    const name = step.name || step.type || 'Pipeline step';
    const parameters = step.parameters && typeof step.parameters === 'object'
      ? JSON.stringify(step.parameters)
      : valueLabel(step.parameters);
    return `<article class="operation-row"><span class="operation-index">${index + 1}</span><div><h4>${escapeHtml(name)}</h4><p>${escapeHtml(operationDescription(step.type))}</p><code>${escapeHtml(parameters)}</code></div><span class="step-status status-${escapeHtml(String(step.status).toLowerCase())}">${escapeHtml(String(step.status).replaceAll('_', ' '))}</span></article>`;
  }).join('');
  let detectionHtml = '';
  if (entries.some(step => step.type === 'objectDetection') &&
      Array.isArray(detectionResults) && detectionResults.length) {
    detectionHtml = `<p class="report-detection-results"><strong>Detection results returned by this job:</strong> ${escapeHtml(JSON.stringify(detectionResults))}</p>`;
  }
  document.getElementById('operation-summary').innerHTML =
    `${operationHtml || '<p class="text-muted">No processing operations were recorded for this run.</p>'}${detectionHtml}`;
}

function renderDifferences(input, output, metrics, executionTime) {
  const outputMetrics = metrics || {};
  const originalDimension = formatDimension(input.width, input.height);
  const processedDimension = formatDimension(outputMetrics.width, outputMetrics.height);
  const dimensionChange = originalDimension !== 'Not available' && processedDimension !== 'Not available'
    ? `${originalDimension} → ${processedDimension}`
    : 'Not available';
  const sizeChange = known(input.size_bytes) && known(output?.size_bytes)
    ? `${formatBytes(input.size_bytes)} → ${formatBytes(output.size_bytes)}`
    : 'Not available';
  const videoStats = String(input.file_type || '').toUpperCase() === 'VIDEO' ? [
    ['Input frame count', input.metadata?.frame_count],
    ['Input FPS', input.metadata?.fps],
    ['Input duration (s)', input.metadata?.duration_seconds],
    ['Output frame count', outputMetrics.frame_count],
    ['Output FPS', outputMetrics.fps],
    ['Output duration (s)', outputMetrics.duration],
    ['Output codec', outputMetrics.output_codec ?? outputMetrics.codec ?? outputMetrics.output_format]
  ].map(([label, value]) => [label, known(value) ? String(value) : 'Not available']) : [];
  const similarityKeys = [
    ['Image similarity (SSIM)', 'ssim'],
    ['Mean squared error (MSE)', 'mse'],
    ['Pixel-level difference', 'pixel_difference']
  ];
  const differenceData = [
    ['Original dimensions', formatDimension(input.width, input.height)],
    ['Output dimensions', formatDimension(outputMetrics.width, outputMetrics.height)],
    ['Original → output dimensions', dimensionChange],
    ['Original → output file size', sizeChange],
    ['Processing duration', known(executionTime) ? `${executionTime} s` : 'Not available'],
    ...videoStats,
    ...similarityKeys.map(([label, key]) => [
      label,
      Object.prototype.hasOwnProperty.call(outputMetrics, key) ? String(outputMetrics[key]) : 'Not available'
    ])
  ];
  document.getElementById('difference-summary').innerHTML = differenceData.map(([label, value]) =>
    `<div class="difference-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  ).join('');
}

function renderMetrics(metrics) {
  const entries = metricEntries(metrics);
  document.getElementById('recorded-metrics').innerHTML = entries.length
    ? entries.map(([key, value]) => `<div class="report-metric"><span>${escapeHtml(metricLabel(key))}</span><strong>${escapeHtml(typeof value === 'object' ? JSON.stringify(value) : value)}</strong></div>`).join('')
    : '<p class="text-muted">No scalar metrics were recorded for this job.</p>';
}

function renderSteps(steps, job, executionTime) {
  const jobStatus = job?.status || 'NOT AVAILABLE';
  const container = document.getElementById('pipeline-steps');
  if (!steps.length) {
    container.innerHTML = '<p class="text-muted">No pipeline nodes were saved with this report.</p>';
    return;
  }
  container.innerHTML = steps.map((step, index) => {
    const status = step.status || 'not_available';
    const parameters = step.parameters && typeof step.parameters === 'object'
      ? JSON.stringify(step.parameters)
      : valueLabel(step.parameters);
    return `<article class="pipeline-step"><span class="pipeline-step-index">${index + 1}</span><div class="pipeline-step-body"><h3>${escapeHtml(step.name || step.type || 'Pipeline node')}</h3><p>${escapeHtml(step.type || 'Node type not available')} · Node ${escapeHtml(step.node_id || 'Not available')}</p><code>${escapeHtml(parameters)}</code></div><span class="step-status status-${escapeHtml(String(status).toLowerCase())}">${escapeHtml(String(status).replaceAll('_', ' '))}</span></article>`;
  }).join('');
  document.getElementById('execution-time').textContent =
    `${statusLabel(jobStatus)} · ${known(executionTime) ? `${executionTime} s` : 'Execution time not available'}`;
}

function statusLabel(value) {
  return String(value || 'NOT AVAILABLE').replaceAll('_', ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function buildConclusion(report, content, input, output, metrics, steps, job, logs, executionTime) {
  const status = job?.status || content.status || 'Not available';
  const pipelineName = content.pipeline?.name || report.pipeline_name || 'Pipeline name not available';
  const applied = steps.filter(step => !['imageSource', 'output'].includes(step.type));
  const operationText = applied.length
    ? `The ${pipelineName} pipeline ran ${applied.map(step => step.name || step.type).filter(Boolean).join(', ')}.`
    : `No processing operation sequence was recorded for the ${pipelineName} pipeline.`;
  const inputText = input.name
    ? `The input was ${input.name}${formatDimension(input.width, input.height) !== 'Not available' ? ` at ${formatDimension(input.width, input.height)}` : ''}.`
    : 'Input file metadata was not available in the report.';
  const outputText = output
    ? `A processed output (${output.filename || 'filename not available'}) is available${formatDimension(metrics.width, metrics.height) !== 'Not available' ? ` at ${formatDimension(metrics.width, metrics.height)}` : ''}.`
    : 'No processed output file is available.';
  const durationText = known(executionTime)
    ? `Recorded processing time was ${executionTime} seconds.`
    : 'Processing duration was not recorded.';
  const limitations = [];
  if (!known(metrics.ssim) && !known(metrics.mse) && !known(metrics.pixel_difference)) {
    limitations.push('No pixel-level difference or similarity metric was recorded.');
  }
  if (!logs.length && !job?.error_message) limitations.push('No execution log details are available.');
  if (job?.error_message || content.error) limitations.push(`Execution error: ${job?.error_message || content.error}`);
  const failedSteps = steps.filter(step => step.status === 'failed');
  if (failedSteps.length) limitations.push(`${failedSteps.length} pipeline step(s) have a recorded failure.`);
  document.getElementById('detail-conclusion').textContent =
    `${statusLabel(status)} job. ${operationText} ${inputText} ${outputText} ${durationText}${limitations.length ? ` Limitations: ${limitations.join(' ')}` : ''}`;
}

function renderReport(report, job) {
  const content = report.content_json || {};
  const pipeline = content.pipeline || {};
  const input = { ...(content.input || {}) };
  const output = content.output && typeof content.output === 'object' ? { ...content.output } : {};
  const result = job?.result || {};
  const metrics = result.metrics || content.metrics || {};
  const inputUrl = job?.input_file_url || input.url;
  const outputUrl = result.output_url || output.url ||
    (typeof content.output === 'string' ? content.output : null);
  const inputType = job?.input_file_type || input.file_type;
  input.file_type = inputType;
  const outputType = result.output_content_type || output.content_type;
  const storedExecutionTime = job?.processing_time ?? content.execution_time;
  const endTime = job?.end_time || content.end_time;
  const executionTime = known(storedExecutionTime) &&
    (known(endTime) || Number(storedExecutionTime) > 0)
    ? storedExecutionTime
    : null;
  const logs = logsArray(job, content);
  const steps = operationSteps(content, job, logs);
  const status = job?.status || content.status || report.job_status;

  document.title = `VisioFlow | ${report.title || 'Processing report'}`;
  document.getElementById('detail-title').textContent = report.title || 'Processing report';
  document.getElementById('detail-summary').textContent = report.summary || 'Detailed analysis generated from the saved job data.';
  document.getElementById('detail-job-id').textContent = job?.id || report.job
    ? `JOB #${job?.id || report.job}` : 'JOB ID NOT AVAILABLE';
  document.getElementById('detail-created').textContent = `Generated ${formatDate(report.created_at)}`;
  document.getElementById('detail-author').textContent = `By ${report.author_name || 'Not available'}`;
  const statusElement = document.getElementById('detail-status');
  statusElement.textContent = statusLabel(status);
  statusElement.className = `report-status status-${statusToken(status)}`;

  document.getElementById('overview-grid').innerHTML = definitionList([
    ['Report ID', report.id],
    ['Project', content.project?.name || report.project_name],
    ['Pipeline', pipeline.name || report.pipeline_name],
    ['Pipeline version', pipeline.version ?? job?.pipeline_version_number ?? report.pipeline_version_number],
    ['Author', report.author_name],
    ['Report generated', formatDate(report.created_at)],
    ['Job status', status],
    ['Input filename', job?.input_file_name || input.name],
    ['Input file type', inputType],
    ['Started', formatDate(job?.start_time || content.start_time)],
    ['Finished', formatDate(job?.end_time || content.end_time)]
  ]);

  document.getElementById('comparison-kind').textContent =
    String(inputType || '').toUpperCase() === 'VIDEO' ? 'Video comparison' : 'Image comparison';
  input.name = job?.input_file_name || input.name;
  input.size_bytes = job?.input_file ? (job.input_file_size ?? input.size_bytes) : input.size_bytes;
  input.width = job?.input_width ?? input.width;
  input.height = job?.input_height ?? input.height;
  input.metadata = { ...(input.metadata || {}) };
  if (job?.input_metadata) input.metadata = { ...input.metadata, ...job.input_metadata };
  output.filename = result.output_filename || output.filename;
  output.size_bytes = result.output_size_bytes ?? output.size_bytes;
  document.getElementById('input-name').textContent = input.name || 'Input file not available';
  document.getElementById('output-name').textContent = output.filename || 'Output file not available';
  renderPreview(document.getElementById('input-preview'), inputUrl, inputType, 'Original input media');
  renderPreview(document.getElementById('output-preview'), outputUrl, outputType || inputType, 'Processed output media');
  document.getElementById('input-metadata').innerHTML = definitionList([
    ['Filename', input.name],
    ['File format', input.format || (input.name?.includes('.') ? input.name.split('.').pop().toUpperCase() : null)],
    ['File type', inputType],
    ['Dimensions', formatDimension(input.width, input.height)],
    ['File size', known(input.size_bytes) ? formatBytes(input.size_bytes) : null],
    ['Video frame count', input.metadata.frame_count],
    ['Video FPS', input.metadata.fps],
    ['Video duration (s)', input.metadata.duration_seconds]
  ]);
  document.getElementById('output-metadata').innerHTML = definitionList([
    ['Filename', output.filename],
    ['File format', output.format || output.filename?.split('.').pop()?.toUpperCase()],
    ['Content type', outputType],
    ['Dimensions', formatDimension(metrics.width, metrics.height)],
    ['File size', known(output.size_bytes) ? formatBytes(output.size_bytes) : null],
    ['Frame count', metrics.frame_count],
    ['FPS', metrics.fps],
    ['Duration (s)', metrics.duration],
    ['Codec', metrics.output_codec ?? metrics.codec ?? metrics.output_format]
  ]);

  const download = document.getElementById('download-output');
  const safeOutputUrl = safeMediaUrl(outputUrl);
  if (safeOutputUrl) {
    const downloadUrl = new URL(safeOutputUrl);
    downloadUrl.searchParams.set('download', '1');
    download.href = downloadUrl.href;
    download.download = output.filename || `visioflow-job-${job?.id || report.job}-output`;
    download.hidden = false;
  } else {
    download.hidden = true;
  }

  renderDifferences(input, output, metrics, executionTime);
  renderOperations(steps, result);
  renderMetrics(metrics);
  renderSteps(steps, job, executionTime);
  document.getElementById('execution-log').textContent = logs.length
    ? logs.join('\n')
    : 'No execution logs were recorded.';
  const messages = [];
  if (job?.error_message || content.error) messages.push(`Error: ${job?.error_message || content.error}`);
  logs.filter(line => /\b(warning|warn|error|failed)\b/i.test(line))
    .forEach(line => messages.push(line));
  const messageBox = document.getElementById('execution-messages');
  messageBox.innerHTML = messages.length
    ? `<strong>Execution warnings and errors</strong><ul>${messages.map(message => `<li>${escapeHtml(message)}</li>`).join('')}</ul>`
    : '';
  messageBox.hidden = !messages.length;
  buildConclusion(report, content, input, output, metrics, steps, job, logs, executionTime);
  document.getElementById('report-detail-loading').hidden = true;
  document.getElementById('report-print-area').hidden = false;
}

function downloadBlob(contents, type, filename) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadReport() {
  const errorBox = document.getElementById('report-detail-error');
  if (!reportId || !/^\d+$/.test(reportId)) {
    document.getElementById('report-detail-loading').hidden = true;
    errorBox.textContent = 'A valid report ID is required.';
    errorBox.hidden = false;
    return;
  }
  try {
    activeReport = await API.getReport(reportId);
    if (activeReport.job) {
      try {
        activeJob = await API.getJob(activeReport.job);
      } catch (error) {
        errorBox.textContent = `Live job details could not be loaded; saved report information is shown. ${error.message}`;
        errorBox.hidden = false;
      }
    }
    renderReport(activeReport, activeJob);
  } catch (error) {
    document.getElementById('report-detail-loading').hidden = true;
    errorBox.textContent = `Report could not be loaded: ${error.message}`;
    errorBox.hidden = false;
  }
}

document.getElementById('export-json').addEventListener('click', () => {
  if (!activeReport) return;
  downloadBlob(JSON.stringify({ report: activeReport, job: activeJob }, null, 2),
    'application/json', `visioflow-report-${activeReport.id}.json`);
});

document.getElementById('export-html').addEventListener('click', () => {
  if (!activeReport) return;
  const title = escapeHtml(activeReport.title || 'Processing report');
  const reportMarkup = document.getElementById('report-print-area').cloneNode(true);
  reportMarkup.hidden = false;
  reportMarkup.querySelectorAll('.report-actions').forEach(element => element.remove());
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${title}</title><style>body{font:15px/1.55 Arial,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#1f2937;background:#fff}section,article{break-inside:avoid}h1,h2,h3{color:#1f2937}.panel,.report-hero,.report-media-card{border:1px solid #f1d8c5;border-radius:10px;padding:18px;margin:14px 0;background:#fff}.report-overview-grid,.report-file-metadata,.difference-grid,.report-metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.report-overview-grid>div,.report-file-metadata>div,.difference-item,.report-metric{padding:10px;background:#fff9f4;border-radius:7px}dt,.report-metric span,.difference-item span{color:#6b7280;font-size:12px}dd{margin:4px 0 0;font-weight:bold}.report-media-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.report-media-preview img,.report-media-preview video{max-width:100%;max-height:440px}.report-media-preview{min-height:120px}.report-steps,.operation-row{border-bottom:1px solid #f1d8c5;padding:12px}.report-json{white-space:pre-wrap;word-break:break-word}.report-status,.step-status{font-weight:bold;color:#c2410c}@media(max-width:650px){.report-media-grid{grid-template-columns:1fr}}</style></head><body><h1>${title}</h1>${reportMarkup.outerHTML}</body></html>`;
  downloadBlob(html, 'text/html', `visioflow-report-${activeReport.id}.html`);
});

document.getElementById('print-report').addEventListener('click', () => window.print());

loadReport();
