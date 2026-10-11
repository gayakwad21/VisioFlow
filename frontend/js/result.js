const jobId = new URLSearchParams(window.location.search).get('id');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function showToast(message, isError = false) {
  const region = document.getElementById('toast-region');
  region.textContent = message;
  region.className = `toast-region visible${isError ? ' error' : ''}`;
  window.setTimeout(() => region.classList.remove('visible'), 3500);
}

function metricCard(label, value) {
  return `<article class="stat-card"><span class="stat-label">${escapeHtml(label)}</span><strong class="stat-value">${escapeHtml(value)}</strong></article>`;
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
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

function videoPreview(url, contentType) {
  return `<video controls preload="metadata"><source src="${escapeHtml(url)}" type="${escapeHtml(contentType)}"></video>`;
}

function showVideoPlaybackError(preview, message) {
  const video = preview.querySelector('video');
  if (!video) return;
  video.addEventListener('error', () => {
    if (preview.querySelector('.video-playback-error')) return;
    const notice = document.createElement('p');
    notice.className = 'video-playback-error';
    notice.setAttribute('role', 'alert');
    notice.textContent = message;
    preview.appendChild(notice);
  });
}

async function loadResult() {
  if (!jobId || !/^\d+$/.test(jobId)) {
    document.getElementById('result-error').hidden = false;
    document.getElementById('result-error').textContent = 'A valid processing job ID is required.';
    return;
  }
  try {
    const job = await API.getJob(jobId);
    const reportButton = document.getElementById('generate-job-report');
    reportButton.disabled = job.status !== 'COMPLETED';
    const pipeline = await API.getPipeline(job.pipeline);
    const result = job.result || {};
    const metrics = result.metrics || {};
    const isVideo = job.input_file_type === 'VIDEO';
    document.getElementById('result-job-id').textContent = `#${job.id}`;
    document.getElementById('result-title').textContent = pipeline.name;
    document.getElementById('result-subtitle').textContent = `${job.project_name} · ${job.status}${job.pipeline_version_number ? ` · version ${job.pipeline_version_number}` : ''} · ${new Date(job.created_at).toLocaleString()} · ${Number(job.processing_time || 0).toFixed(3)} seconds`;
    const versionQuery = job.pipeline_version ? `&version=${encodeURIComponent(job.pipeline_version)}` : '';
    document.getElementById('edit-pipeline-link').href = `/pipeline-editor.html?project=${encodeURIComponent(job.project)}&pipeline=${encodeURIComponent(pipeline.id)}${versionQuery}`;

    const metricCards = [
      metricCard('Status', job.status),
      metricCard('Execution time', `${Number(job.processing_time || 0).toFixed(3)} s`),
      metricCard('Output dimensions', metrics.width && metrics.height ? `${metrics.width} × ${metrics.height}` : '—'),
    ];
    if (isVideo) {
      metricCards.push(
        metricCard('FPS', metrics.fps ?? '—'),
        metricCard('Frame count', metrics.frame_count ?? '—'),
        metricCard('Output format', metrics.output_format || 'MP4'),
        metricCard('Output size', formatBytes(result.output_size_bytes ?? metrics.output_size_bytes))
      );
    } else {
      metricCards.push(
        metricCard('Brightness / contrast', metrics.brightness !== undefined ? `${metrics.brightness} / ${metrics.contrast}` : '—'),
        metricCard('Sharpness', metrics.sharpness ?? '—'),
        metricCard('Edge density', metrics.edge_density ?? '—')
      );
    }
    document.getElementById('result-metrics').innerHTML = metricCards.join('');

    const inputPreview = document.getElementById('original-preview');
    if (job.input_file_url) {
      inputPreview.innerHTML = isVideo
        ? `<span class="result-media-name">${escapeHtml(job.input_file_name || 'Original video')}</span>${videoPreview(job.input_file_url, job.input_file_content_type || 'video/mp4')}`
        : `<a href="${escapeHtml(job.input_file_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(job.input_file_url)}" alt="Original input"></a>`;
      if (isVideo) {
        document.getElementById('original-preview-title').textContent = 'Original Video';
        showVideoPlaybackError(inputPreview, 'Original video could not be played by this browser.');
      }
    }
    const outputPreview = document.getElementById('output-preview');
    if (result.output_url) {
      outputPreview.innerHTML = isVideo
        ? videoPreview(result.output_url, result.output_content_type || 'video/mp4')
        : `<a href="${escapeHtml(result.output_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(result.output_url)}" alt="Processed output"></a>`;
      if (isVideo) {
        document.getElementById('output-preview-title').textContent = 'Processed Video';
        showVideoPlaybackError(
          outputPreview,
          'Processed video could not be played by this browser. Check the encoding/codec.'
        );
      }
    } else if (job.error_message) {
      outputPreview.textContent = job.error_message;
    }

    const nodes = job.pipeline_graph?.nodes || pipeline.graph_data?.nodes || [];
    document.getElementById('result-pipeline-title').textContent = pipeline.name;
    document.getElementById('result-steps').innerHTML = nodes.length
      ? nodes.map((node, index) => {
        const data = { ...(node.data || {}) };
        if (node.type === 'imageSource' && job.input_file_name) data.imageName = job.input_file_name;
        return `<div class="simple-list-row"><span class="project-mark">${index + 1}</span><span><strong>${escapeHtml(node.type)}</strong><small>${escapeHtml(JSON.stringify(data))}</small></span></div>`;
      }).join('')
      : '<div class="empty-state compact"><strong>No pipeline nodes</strong><span>This saved graph has no configured steps.</span></div>';
    document.getElementById('result-logs').textContent = (result.logs || []).join('\n') || job.error_message || 'No processing logs are available.';
    if (job.status === 'QUEUED' || job.status === 'PROCESSING') {
      window.setTimeout(loadResult, 2000);
    }
  } catch (error) {
    const box = document.getElementById('result-error');
    box.hidden = false;
    box.textContent = `Result could not be loaded: ${error.message}`;
  }
}

document.getElementById('generate-job-report').addEventListener('click', async () => {
  try {
    document.getElementById('generate-job-report').disabled = true;
    const report = await API.generateReport(jobId);
    showToast('Report generated.');
    window.location.href = `/reports.html?report=${encodeURIComponent(report.id)}`;
  } catch (error) {
    showToast(error.message, true);
    document.getElementById('generate-job-report').disabled = false;
  }
});

loadResult();
