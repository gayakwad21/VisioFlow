const API_BASE = '/api';

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function apiRequest(endpoint, method = 'GET', data = null, isFormData = false) {
  const options = {
    method,
    headers: {},
    credentials: 'same-origin'
  };

  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    options.headers['X-CSRFToken'] = csrftoken;
  }

  if (data) {
    if (isFormData) {
      options.body = data;
    } else {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(data);
    }
  }

  const res = await fetch(`${API_BASE}${endpoint}`, options);
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    const json = await res.json();
    if (!res.ok) {
      const detail = json.detail || json.message || json.error;
      const message = detail || Object.entries(json)
        .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
        .join('; ') || `API request failed (${res.status})`;
      const error = new Error(message);
      error.status = res.status;
      if ((res.status === 401 || res.status === 403) &&
          /authentication credentials were not provided|not authenticated/i.test(String(detail || ''))) {
        const publicPage = /login\.html|register\.html/.test(window.location.pathname) || window.location.pathname === '/';
        if (!publicPage) window.location.href = '/login.html';
      }
      throw error;
    }
    return json;
  }

  if (!res.ok) {
    const error = new Error(`HTTP Error ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return await res.text();
}

const API = {
  // Auth
  register: (username, email, password) => apiRequest('/auth/register/', 'POST', { username, email, password }),
  login: (username, password) => apiRequest('/auth/login/', 'POST', { username, password }),
  logout: () => apiRequest('/auth/logout/', 'POST'),
  getProfile: () => apiRequest('/auth/profile/'),

  // Projects
  getProjects: () => apiRequest('/projects/'),
  searchProjects: (search) => apiRequest(`/projects/?search=${encodeURIComponent(search)}`),
  createProject: (name, description) => apiRequest('/projects/', 'POST', { name, description }),
  getProject: (id) => apiRequest(`/projects/${id}/`),
  updateProject: (id, fields) => apiRequest(`/projects/${id}/`, 'PATCH', fields),
  deleteProject: (id) => apiRequest(`/projects/${id}/`, 'DELETE'),

  // Files
  uploadFile: (projectId, file) => {
    const formData = new FormData();
    formData.append('project', projectId);
    formData.append('file', file);
    return apiRequest('/files/', 'POST', formData, true);
  },
  getFiles: (projectId) => apiRequest(`/files/${projectId ? `?project=${encodeURIComponent(projectId)}` : ''}`),
  deleteFile: (id) => apiRequest(`/files/${id}/`, 'DELETE'),

  // Pipelines
  getPipelines: () => apiRequest('/pipelines/'),
  createPipeline: (projectId, name, description, graphData) => apiRequest('/pipelines/', 'POST', { project: projectId, name, description, graph_data: graphData }),
  getPipeline: (id) => apiRequest(`/pipelines/${id}/`),
  updatePipeline: (id, name, description, graphData) => apiRequest(`/pipelines/${id}/`, 'PATCH', { name, description, graph_data: graphData }),
  runPipeline: (id, inputFileId, versionId) => apiRequest(`/pipelines/${id}/run/`, 'POST', { input_file_id: inputFileId, version_id: versionId }),
  savePipelineVersion: (id, name, description) => apiRequest(`/pipelines/${id}/save-version/`, 'POST', { name, description }),
  getPipelineVersions: (id) => apiRequest(`/pipelines/${id}/versions/`),
  restorePipelineVersion: (id, versionId) => apiRequest(`/pipelines/${id}/restore-version/`, 'POST', { version_id: versionId }),
  exportPythonCode: (id) => apiRequest(`/pipelines/${id}/export-python/`),
  generateAIPipeline: (prompt) => apiRequest('/pipelines/generate-ai/', 'POST', { prompt }),
  getTemplates: () => apiRequest('/templates/'),
  getTemplate: (id) => apiRequest(`/templates/${id}/`),

  // Processing & Experiments
  getJobs: () => apiRequest('/jobs/'),
  getJob: (id) => apiRequest(`/jobs/${id}/`),
  retryJob: (id) => apiRequest(`/jobs/${id}/retry/`, 'POST'),
  getExperiments: () => apiRequest('/experiments/'),
  createExperiment: (projectId, name, jobAId, jobBId) => apiRequest('/experiments/', 'POST', { project: projectId, name, job_a: jobAId, job_b: jobBId }),

  // Reports & Analytics
  getReports: () => apiRequest('/reports/'),
  getReport: (id) => apiRequest(`/reports/${encodeURIComponent(id)}/`),
  generateReport: (jobId) => apiRequest('/reports/generate/', 'POST', { job_id: jobId }),
  createReport: (projectId, pipelineId, jobId, title, summary) => apiRequest('/reports/', 'POST', { project: projectId, pipeline: pipelineId, job: jobId, title, summary }),
  getDashboardStats: () => apiRequest('/analytics/dashboard/'),
};
