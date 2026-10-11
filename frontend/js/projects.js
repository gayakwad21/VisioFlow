const projectGrid = document.getElementById('projects-grid');
const projectModal = document.getElementById('project-modal');
const projectForm = document.getElementById('project-form');
let editingProjectId = null;
let searchTimer;

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

function formatDate(value) {
  return value ? new Date(value).toLocaleDateString() : '—';
}

function openModal(project = null) {
  editingProjectId = project?.id ?? null;
  document.getElementById('project-modal-title').textContent = project ? 'Rename project' : 'Create project';
  document.getElementById('project-submit').textContent = project ? 'Save changes' : 'Create project';
  document.getElementById('project-name').value = project?.name ?? '';
  document.getElementById('project-description').value = project?.description ?? '';
  projectModal.classList.add('active');
  document.getElementById('project-name').focus();
}

function closeModal() {
  projectModal.classList.remove('active');
  projectForm.reset();
  editingProjectId = null;
}

function renderProjects(projects) {
  document.getElementById('project-count').textContent = `${projects.length} ${projects.length === 1 ? 'project' : 'projects'}`;
  if (!projects.length) {
    projectGrid.innerHTML = '<div class="empty-state project-empty"><strong>No projects found</strong><span>Create a project or try a different search.</span><button class="btn btn-primary" id="empty-create-project">＋ New project</button></div>';
    document.getElementById('empty-create-project')?.addEventListener('click', () => openModal());
    return;
  }
  projectGrid.innerHTML = projects.map(project => `
    <article class="project-card">
      <div class="project-card-top"><span class="project-mark">▦</span><span class="project-updated">Updated ${formatDate(project.updated_at)}</span></div>
      <a class="project-title" href="/project-detail.html?id=${encodeURIComponent(project.id)}">${escapeHtml(project.name)}</a>
      <p class="project-description">${escapeHtml(project.description || 'No description added.')}</p>
      <div class="project-metrics"><span><strong>${project.file_count ?? 0}</strong> files</span><span><strong>${project.pipeline_count ?? 0}</strong> pipelines</span><span>Created ${formatDate(project.created_at)}</span></div>
      <div class="project-card-actions">
        <a href="/project-detail.html?id=${encodeURIComponent(project.id)}" class="btn btn-primary">Open project</a>
        <a href="/pipeline-editor.html?project=${encodeURIComponent(project.id)}" class="btn btn-secondary">New pipeline</a>
      </div>
      <div class="project-card-footer">
        <button type="button" class="text-button" data-rename="${project.id}">Rename</button>
        <label class="text-button upload-control">Upload media<input type="file" data-upload-project="${project.id}" accept=".jpg,.jpeg,.png,.bmp,.webp,.mp4,.avi,.mov,.mkv,.webm"></label>
        <button type="button" class="text-button text-danger" data-delete="${project.id}">Delete</button>
      </div>
    </article>`).join('');
}

async function loadProjects(search = '') {
  projectGrid.innerHTML = '<div class="loading-state">Loading your projects…</div>';
  document.getElementById('project-error').hidden = true;
  try {
    renderProjects(await API.searchProjects(search));
  } catch (error) {
    projectGrid.innerHTML = '<div class="empty-state"><strong>Projects could not be loaded</strong><span>Check your connection and try refreshing.</span><button type="button" class="btn btn-secondary" id="retry-projects">Retry</button></div>';
    document.getElementById('project-error').textContent = error.message;
    document.getElementById('project-error').hidden = false;
    document.getElementById('retry-projects')?.addEventListener('click', () => loadProjects(search));
  }
}

document.getElementById('new-project-btn').addEventListener('click', () => openModal());
document.querySelectorAll('[data-close-modal]').forEach(button => button.addEventListener('click', closeModal));
projectModal.addEventListener('click', event => {
  if (event.target === projectModal) closeModal();
});

projectForm.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = document.getElementById('project-submit');
  submit.disabled = true;
  try {
    const name = document.getElementById('project-name').value.trim();
    const description = document.getElementById('project-description').value.trim();
    if (editingProjectId) {
      await API.updateProject(editingProjectId, { name, description });
      showToast('Project updated.');
    } else {
      await API.createProject(name, description);
      showToast('Project created.');
    }
    closeModal();
    await loadProjects(document.getElementById('project-search').value.trim());
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

document.getElementById('project-search').addEventListener('input', event => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadProjects(event.target.value.trim()), 220);
});

projectGrid.addEventListener('click', async event => {
  const renameButton = event.target.closest('[data-rename]');
  const deleteButton = event.target.closest('[data-delete]');
  if (renameButton) {
    try {
      const project = await API.getProject(renameButton.dataset.rename);
      openModal(project);
    } catch (error) {
      showToast(error.message, true);
    }
  }
  if (deleteButton) {
    if (!window.confirm('Delete this project and its files, pipelines, and jobs? This cannot be undone.')) return;
    deleteButton.disabled = true;
    try {
      await API.deleteProject(deleteButton.dataset.delete);
      showToast('Project deleted.');
      await loadProjects(document.getElementById('project-search').value.trim());
    } catch (error) {
      showToast(error.message, true);
      deleteButton.disabled = false;
    }
  }
});

projectGrid.addEventListener('change', async event => {
  const input = event.target.closest('[data-upload-project]');
  const file = input?.files?.[0];
  if (!file) return;
  const label = input.closest('label');
  label.classList.add('is-uploading');
  try {
    await API.uploadFile(input.dataset.uploadProject, file);
    showToast(`${file.name} uploaded.`);
    await loadProjects(document.getElementById('project-search').value.trim());
  } catch (error) {
    showToast(error.message, true);
    input.value = '';
  } finally {
    label.classList.remove('is-uploading');
  }
});

loadProjects();
if (new URLSearchParams(window.location.search).get('create') === '1') openModal();
