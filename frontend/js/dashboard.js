function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function dateLabel(value) {
  return value ? new Date(value).toLocaleString() : '—';
}

function statusBadge(status) {
  const normalized = String(status || 'QUEUED').toLowerCase();
  return `<span class="badge badge-${escapeHtml(normalized)}">${escapeHtml(status || 'QUEUED')}</span>`;
}

document.addEventListener('DOMContentLoaded', async () => {
  const errorBox = document.getElementById('dashboard-error');
  try {
    const [user, stats] = await Promise.all([API.getProfile(), API.getDashboardStats()]);
    document.getElementById('user-display').textContent = `👤 ${user.username}`;
    document.getElementById('stat-projects').textContent = stats.projects_count ?? 0;
    document.getElementById('stat-pipelines').textContent = stats.pipelines_count ?? 0;
    document.getElementById('stat-jobs').textContent = stats.jobs_count ?? 0;
    document.getElementById('stat-completed').textContent = stats.completed_jobs ?? 0;
    document.getElementById('stat-failed').textContent = stats.failed_jobs ?? 0;

    const projects = document.getElementById('recent-projects');
    if (stats.recent_projects?.length) {
      projects.innerHTML = stats.recent_projects.map(project => `
        <a class="project-row" href="/project-detail.html?id=${encodeURIComponent(project.id)}">
          <span class="project-mark">▦</span><span class="project-row-main">
            <strong>${escapeHtml(project.name)}</strong>
            <small>${escapeHtml(project.description || 'No description')} · Updated ${dateLabel(project.updated_at)}</small>
          </span><span class="project-row-counts">${project.file_count ?? 0} files · ${project.pipeline_count ?? 0} pipelines</span>
        </a>`).join('');
    } else {
      projects.innerHTML = '<div class="empty-state"><strong>No projects yet</strong><span>Create a project to organize media and pipelines.</span><a class="btn btn-primary" href="/projects.html?create=1">Create your first project</a></div>';
    }

    const jobs = document.getElementById('recent-jobs');
    if (stats.recent_jobs?.length) {
      jobs.innerHTML = `<table><thead><tr><th>Pipeline</th><th>Project</th><th>Status</th><th>Run time</th></tr></thead><tbody>${stats.recent_jobs.map(job => `
        <tr><td>${escapeHtml(job.pipeline_name || 'Pipeline')}</td><td>${escapeHtml(job.project_name || '—')}</td>
        <td>${statusBadge(job.status)}</td><td>${dateLabel(job.created_at)}</td></tr>`).join('')}</tbody></table>`;
    } else {
      jobs.innerHTML = '<div class="empty-state compact"><strong>No processing jobs</strong><span>Run a saved pipeline to see execution results here.</span></div>';
    }

    const activity = document.getElementById('recent-activity');
    if (stats.recent_activities?.length) {
      activity.innerHTML = stats.recent_activities.map(entry => `
        <div class="activity-row"><span class="activity-dot"></span><div><strong>${escapeHtml(entry.action.replaceAll('_', ' ').toLowerCase())}</strong>
        <small>${escapeHtml(entry.username || user.username)} · ${dateLabel(entry.created_at)}</small></div></div>`).join('');
    } else {
      activity.innerHTML = '<div class="empty-state compact"><strong>No activity recorded</strong><span>Your project and pipeline actions will appear here.</span></div>';
    }
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = `Dashboard data could not be loaded: ${error.message}`;
    for (const id of ['recent-projects', 'recent-jobs', 'recent-activity']) {
      document.getElementById(id).innerHTML = '<div class="empty-state compact"><strong>Unable to load data</strong><span>Refresh the page or try again shortly.</span></div>';
    }
  }

  document.getElementById('logout-btn').addEventListener('click', async () => {
    try {
      await API.logout();
      window.location.href = '/login.html';
    } catch (error) {
      const region = document.getElementById('toast-region');
      region.textContent = `Could not log out: ${error.message}`;
      region.classList.add('visible');
    }
  });
});
