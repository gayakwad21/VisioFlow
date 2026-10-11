const reportList = document.getElementById('reports-list');
let reports = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function dateLabel(value) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString();
}

function statusLabel(value) {
  return String(value || 'NOT AVAILABLE').replaceAll('_', ' ').toLowerCase()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function statusToken(value) {
  return String(value || 'not_available').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
}

function operationDescription(type) {
  const descriptions = {
    grayscale: 'Converts a colour image to grayscale.',
    blur: 'Reduces fine detail and noise using the configured blur operation.',
    gaussianBlur: 'Reduces high-frequency detail and noise with a Gaussian kernel.',
    medianBlur: 'Reduces impulse noise while preserving many edges.',
    canny: 'Highlights strong image edges; it does not identify objects.',
    threshold: 'Separates pixels using the configured intensity threshold.',
    adaptiveThreshold: 'Thresholds regions using their local intensity.',
    morphological: 'Applies the configured erosion, dilation, opening, or closing operation.',
    rotate: 'Rotates the image by the configured angle.',
    resize: 'Resizes the image to the configured dimensions.',
    crop: 'Crops the image to the configured region.',
    brightness: 'Adjusts image brightness and contrast.',
    sharpen: 'Increases local edge contrast to sharpen the image.',
    findContours: 'Finds image contours; this is not object classification.',
    histogram: 'Calculates image intensity distribution data.',
    imageStatistics: 'Calculates image statistics.',
    objectDetection: 'Runs the configured object-detection operation; results are listed only if returned by the job.'
  };
  return descriptions[type] || 'Applied the recorded pipeline operation.';
}

function reportSummary(report) {
  const stored = String(report.summary || '').trim();
  if (stored && !/^completed run for /i.test(stored) && !/^completed run\.$/i.test(stored)) {
    return stored;
  }

  const content = report.content_json || {};
  const pipeline = content.pipeline?.name || report.pipeline_name || 'Pipeline';
  const input = content.input?.name;
  const steps = (content.pipeline?.steps || [])
    .filter(step => !['imageSource', 'output'].includes(step.type))
    .map(step => operationDescription(step.type));
  const details = [];
  if (steps.length) details.push(steps.join(' '));
  else details.push('No processing operation details were recorded.');
  if (input) details.push(`Input: ${input}.`);
  if (content.status || report.job_status) details.push(`Job status: ${statusLabel(content.status || report.job_status)}.`);
  return `${pipeline}: ${details.join(' ')}`;
}

function renderReports() {
  const term = document.getElementById('reports-search').value.trim().toLowerCase();
  const status = document.getElementById('reports-status').value;
  const visible = reports.filter(report => {
    const content = report.content_json || {};
    const jobStatus = content.status || report.job_status || '';
    const haystack = [
      report.title, report.project_name, report.pipeline_name, report.job, content.input?.name,
      reportSummary(report)
    ].join(' ').toLowerCase();
    return (!term || haystack.includes(term)) && (!status || jobStatus === status);
  });

  document.getElementById('report-count').textContent =
    `${visible.length} ${visible.length === 1 ? 'report' : 'reports'}`;
  if (!visible.length) {
    reportList.innerHTML = `<div class="empty-state report-empty"><strong>${reports.length ? 'No matching reports' : 'No reports yet'}</strong><span>${reports.length ? 'Try changing your search or status filter.' : 'Generate a report from one of your processing jobs to see its full analysis here.'}</span></div>`;
    return;
  }

  reportList.innerHTML = visible.map(report => {
    const content = report.content_json || {};
    const statusValue = content.status || report.job_status || 'NOT AVAILABLE';
    const pipelineName = content.pipeline?.name || report.pipeline_name || 'Pipeline unavailable';
    const version = content.pipeline?.version ?? report.pipeline_version_number;
    return `<article class="report-card">
      <div class="report-card-icon" aria-hidden="true">▤</div>
      <div class="report-card-main">
        <div class="report-card-heading"><h2>${escapeHtml(report.title || 'Untitled report')}</h2><span class="report-status status-${statusToken(statusValue)}">${escapeHtml(statusLabel(statusValue))}</span></div>
        <p class="report-card-summary">${escapeHtml(reportSummary(report))}</p>
        <div class="report-card-meta">
          <span><strong>Project</strong>${escapeHtml(content.project?.name || report.project_name || 'Not available')}</span>
          <span><strong>Pipeline / job</strong>${escapeHtml(pipelineName)}${version ? ` · v${escapeHtml(version)}` : ''}${report.job ? ` · #${escapeHtml(report.job)}` : ''}</span>
          <span><strong>Created</strong>${escapeHtml(dateLabel(report.created_at))}</span>
        </div>
      </div>
      <a class="btn btn-primary report-view-action" href="/report-detail.html?id=${encodeURIComponent(report.id)}">View report <span aria-hidden="true">→</span></a>
    </article>`;
  }).join('');
}

async function loadReports() {
  reportList.innerHTML = '<div class="loading-state">Loading your reports…</div>';
  const errorBox = document.getElementById('reports-error');
  errorBox.hidden = true;
  try {
    reports = await API.getReports();
    renderReports();
  } catch (error) {
    document.getElementById('report-count').textContent = '';
    reportList.innerHTML = '<div class="empty-state"><strong>Reports could not be loaded</strong><span>Check your connection and try again.</span></div>';
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
}

document.getElementById('reports-search').addEventListener('input', renderReports);
document.getElementById('reports-status').addEventListener('change', renderReports);
document.getElementById('new-report-btn').addEventListener('click', async () => {
  const modal = document.getElementById('report-modal');
  const select = document.getElementById('report-job-select');
  const errorBox = document.getElementById('report-modal-error');
  select.innerHTML = '<option value="">Loading jobs…</option>';
  modal.classList.add('active');
  errorBox.hidden = true;
  try {
    const jobs = await API.getJobs();
    select.innerHTML = jobs.length
      ? jobs.map(job => `<option value="${escapeHtml(job.id)}">#${escapeHtml(job.id)} · ${escapeHtml(job.pipeline_name)} · ${escapeHtml(statusLabel(job.status))} · ${escapeHtml(dateLabel(job.created_at))}</option>`).join('')
      : '<option value="">No jobs available</option>';
  } catch (error) {
    select.innerHTML = '<option value="">Could not load jobs</option>';
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
});

document.querySelectorAll('[data-close-report]').forEach(button => {
  button.addEventListener('click', () => document.getElementById('report-modal').classList.remove('active'));
});

document.getElementById('generate-report-submit').addEventListener('click', async event => {
  const jobId = document.getElementById('report-job-select').value;
  if (!jobId) return;
  const button = event.currentTarget;
  const errorBox = document.getElementById('report-modal-error');
  button.disabled = true;
  errorBox.hidden = true;
  try {
    const report = await API.generateReport(jobId);
    window.location.href = `/report-detail.html?id=${encodeURIComponent(report.id)}`;
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    button.disabled = false;
  }
});

const oldReportId = new URLSearchParams(window.location.search).get('report');
if (oldReportId && /^\d+$/.test(oldReportId)) {
  window.location.replace(`/report-detail.html?id=${encodeURIComponent(oldReportId)}`);
} else {
  loadReports();
}
