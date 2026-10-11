const projectId = new URLSearchParams(window.location.search).get('id');
let currentProject;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function notify(message, isError = false) {
  const region = document.getElementById('toast-region');
  region.textContent = message;
  region.className = `toast-region visible${isError ? ' error' : ''}`;
  window.setTimeout(() => region.classList.remove('visible'), 3500);
}

function showFailure(message) {
  const box = document.getElementById('workspace-error');
  box.textContent = message;
  box.hidden = false;
}

function renderFiles(files) {
  const container = document.getElementById('workspace-files');
  document.getElementById('workspace-files-count').textContent = files.length;
  if (!files.length) {
    container.innerHTML = '<div class="empty-state"><strong>No media uploaded</strong><span>Upload an image or video to start building a vision workflow.</span></div>';
    return;
  }
  container.innerHTML = files.map(file => `
    <article class="media-card">
      <div class="media-preview">
        ${file.file_type === 'IMAGE'
          ? `<a href="${escapeHtml(file.file_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(file.file_url)}" alt="${escapeHtml(file.original_name)}" loading="lazy"></a>`
          : `<video src="${escapeHtml(file.file_url)}" controls preload="metadata" aria-label="${escapeHtml(file.original_name)}"></video>`}
      </div>
      <div class="media-card-body"><div class="media-title"><strong title="${escapeHtml(file.original_name)}">${escapeHtml(file.original_name)}</strong><span class="badge badge-processing">${escapeHtml(file.file_type)}</span></div>
        <p>${formatBytes(file.file_size)}${file.width && file.height ? ` · ${file.width} × ${file.height}px · ${file.channels} ch` : ''}${file.file_type === 'VIDEO' && file.metadata?.duration_seconds ? ` · ${Number(file.metadata.duration_seconds).toFixed(1)}s · ${Number(file.metadata.fps || 0).toFixed(1)} FPS` : ''}</p>
        <small>Uploaded ${new Date(file.created_at).toLocaleString()}</small>
        <div class="media-actions"><a class="btn btn-primary" href="/pipeline-editor.html?project=${encodeURIComponent(projectId)}&input_file=${encodeURIComponent(file.id)}">Use in pipeline</a>
        <button class="btn btn-danger" type="button" data-delete-file="${file.id}">Delete</button></div>
      </div>
    </article>`).join('');
}

function renderPipelines(pipelines) {
  const container = document.getElementById('workspace-pipelines');
  document.getElementById('workspace-pipelines-count').textContent = pipelines.length;
  if (!pipelines.length) {
    container.innerHTML = '<div class="empty-state compact"><strong>No pipelines in this project</strong><span>Build and save a visual workflow here.</span></div>';
    return;
  }
  container.innerHTML = pipelines.map(pipeline => `
    <a class="simple-list-row" href="/pipeline-editor.html?project=${encodeURIComponent(projectId)}&pipeline=${encodeURIComponent(pipeline.id)}">
      <span class="project-mark">⌘</span><span><strong>${escapeHtml(pipeline.name)}</strong><small>${escapeHtml(pipeline.description || 'No description')} · Updated ${new Date(pipeline.updated_at).toLocaleDateString()}</small></span><span>→</span>
    </a>`).join('');
}

function renderJobs(jobs) {
  const container = document.getElementById('workspace-jobs');
  const projectJobs = jobs.filter(job => String(job.project) === String(projectId));
  document.getElementById('workspace-jobs-count').textContent = projectJobs.length;
  document.getElementById('workspace-completed-count').textContent = projectJobs.filter(job => job.status === 'COMPLETED').length;
  if (!projectJobs.length) {
    container.innerHTML = '<div class="empty-state compact"><strong>No processing runs yet</strong><span>Run a pipeline to create the first job record.</span></div>';
    return;
  }
  container.innerHTML = projectJobs.slice(0, 8).map(job => `
    <div class="simple-list-row"><span class="project-mark">◷</span><span><strong>${escapeHtml(job.pipeline_name || 'Pipeline')}</strong><small>${new Date(job.created_at).toLocaleString()} · ${Number(job.processing_time || 0).toFixed(2)}s</small></span><span class="badge badge-${escapeHtml(String(job.status).toLowerCase())}">${escapeHtml(job.status)}</span></div>`).join('');
}

async function loadWorkspace() {
  if (!projectId || !/^\d+$/.test(projectId)) {
    showFailure('A valid project ID is required. Return to the projects page and open a project.');
    document.getElementById('workspace-files').innerHTML = '';
    return;
  }
  try {
    const [project, files, pipelines, jobs] = await Promise.all([
      API.getProject(projectId), API.getFiles(projectId), API.getPipelines(), API.getJobs()
    ]);
    currentProject = project;
    document.title = `${project.name} | VisioFlow`;
    document.getElementById('project-breadcrumb').textContent = project.name;
    document.getElementById('workspace-title').textContent = project.name;
    document.getElementById('workspace-description').textContent = project.description || 'No project description.';
    document.getElementById('workspace-dates').textContent = `Created ${new Date(project.created_at).toLocaleDateString()} · Updated ${new Date(project.updated_at).toLocaleDateString()}`;
    const editorUrl = `/pipeline-editor.html?project=${encodeURIComponent(projectId)}`;
    document.getElementById('new-pipeline-link').href = editorUrl;
    document.getElementById('pipelines-editor-link').href = editorUrl;
    renderFiles(files);
    renderPipelines(pipelines.filter(pipeline => String(pipeline.project) === String(projectId)));
    renderJobs(jobs);
  } catch (error) {
    showFailure(`Project workspace could not be loaded: ${error.message}`);
  }
}

document.getElementById('media-upload').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  const status = document.getElementById('upload-status');
  status.textContent = `Uploading ${file.name}…`;
  event.target.disabled = true;
  try {
    await API.uploadFile(projectId, file);
    status.textContent = '';
    notify('Media uploaded successfully.');
    await loadWorkspace();
  } catch (error) {
    status.textContent = error.message;
    status.classList.add('error-text');
  } finally {
    event.target.disabled = false;
    event.target.value = '';
  }
});

document.getElementById('workspace-files').addEventListener('click', async event => {
  const button = event.target.closest('[data-delete-file]');
  if (!button || !window.confirm('Delete this uploaded file?')) return;
  button.disabled = true;
  try {
    await API.deleteFile(button.dataset.deleteFile);
    notify('File deleted.');
    await loadWorkspace();
  } catch (error) {
    notify(error.message, true);
    button.disabled = false;
  }
});

const projectModal = document.getElementById('project-modal');
document.getElementById('rename-project-btn').addEventListener('click', () => {
  if (!currentProject) return;
  document.getElementById('project-name').value = currentProject.name;
  document.getElementById('project-description').value = currentProject.description || '';
  projectModal.classList.add('active');
});
document.querySelectorAll('[data-close-modal]').forEach(button => button.addEventListener('click', () => projectModal.classList.remove('active')));
document.getElementById('project-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('save-project-btn');
  button.disabled = true;
  try {
    await API.updateProject(projectId, {
      name: document.getElementById('project-name').value.trim(),
      description: document.getElementById('project-description').value.trim()
    });
    projectModal.classList.remove('active');
    notify('Project settings saved.');
    await loadWorkspace();
  } catch (error) {
    notify(error.message, true);
  } finally {
    button.disabled = false;
  }
});

loadWorkspace();
