const API = window.location.origin;
let token = localStorage.getItem('foxai_token');
let currentUser = JSON.parse(localStorage.getItem('foxai_user') || 'null');

// ── Auth ─────────────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

async function login() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  try {
    const data = await api('POST', '/auth/login', { email, password });
    token = data.access_token;
    currentUser = data.user;
    localStorage.setItem('foxai_token', token);
    localStorage.setItem('foxai_user', JSON.stringify(currentUser));
    showApp();
  } catch (e) {
    errEl.textContent = '⚠️ ' + e.message;
    errEl.classList.remove('hidden');
  }
}

function logout() {
  localStorage.removeItem('foxai_token');
  localStorage.removeItem('foxai_user');
  token = null; currentUser = null;
  document.getElementById('app-screen').classList.add('hidden');
  document.getElementById('login-screen').classList.remove('hidden');
}

function showApp() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
  document.getElementById('user-name').textContent = currentUser?.full_name || '';
  // Show create button for admin/manager
  if (currentUser?.role !== 'member') {
    document.getElementById('create-btn').classList.remove('hidden');
  }
  showTab('tasks');
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

function showTab(name) {
  ['tasks', 'standup', 'weekly'].forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('hidden', t !== name);
    document.getElementById('nav-' + t).classList.toggle('active', t === name);
  });
  if (name === 'tasks') loadTasks();
  if (name === 'standup') loadStandup();
  if (name === 'weekly') loadWeekly();
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

async function loadTasks() {
  const status = document.getElementById('filter-status').value;
  const search = document.getElementById('filter-search').value;
  let url = '/tasks?';
  if (status) url += `status=${status}&`;
  if (search) url += `search=${encodeURIComponent(search)}&`;

  const container = document.getElementById('tasks-container');
  container.innerHTML = '<p class="loading">Đang tải...</p>';

  try {
    const tasks = await api('GET', url);
    if (!tasks.length) {
      container.innerHTML = '<p class="loading">Không có task nào.</p>';
      return;
    }
    container.innerHTML = tasks.map(renderTask).join('');
  } catch (e) {
    container.innerHTML = `<p class="error">Lỗi: ${e.message}</p>`;
  }
}

function renderTask(t) {
  const today = new Date().toISOString().split('T')[0];
  const isOverdue = t.deadline && t.deadline < today && t.status !== 'completed';
  const statusLabel = { pending: 'Chờ', in_progress: 'Đang làm', completed: 'Xong' };
  const deadlineStr = t.deadline ? new Date(t.deadline + 'T00:00:00').toLocaleDateString('vi-VN') : 'N/A';
  const overdueDays = isOverdue
    ? Math.floor((new Date() - new Date(t.deadline)) / 86400000)
    : 0;

  const canEdit = currentUser?.role !== 'member' || t.owner_id === currentUser?.id;

  return `
    <div class="task-card status-${t.status}${isOverdue ? ' overdue' : ''}" id="task-${t.id}">
      <div class="task-info">
        <div class="task-title">
          <span class="task-id">#${t.id}</span> ${escHtml(t.title)}
          ${t.project ? `<small style="color:#9e9e9e"> · ${escHtml(t.project)}</small>` : ''}
        </div>
        <div class="task-meta">
          <span>👤 ${escHtml(t.owner_name || '—')}</span>
          <span>📅 ${deadlineStr}${isOverdue ? ` <strong style="color:var(--overdue)">Trễ ${overdueDays} ngày!</strong>` : ''}</span>
          ${t.notes ? `<span>📝 ${escHtml(t.notes.substring(0, 60))}${t.notes.length > 60 ? '…' : ''}</span>` : ''}
        </div>
      </div>
      <span class="badge badge-${t.status}">${statusLabel[t.status]}</span>
      ${canEdit ? `
      <div class="task-actions">
        <select onchange="updateStatus(${t.id}, this.value)" title="Đổi trạng thái">
          <option value="">Trạng thái</option>
          <option value="pending"${t.status === 'pending' ? ' selected' : ''}>⏳ Chờ</option>
          <option value="in_progress"${t.status === 'in_progress' ? ' selected' : ''}>🔵 Đang làm</option>
          <option value="completed"${t.status === 'completed' ? ' selected' : ''}>✅ Xong</option>
        </select>
      </div>` : ''}
    </div>`;
}

async function updateStatus(taskId, status) {
  if (!status) return;
  try {
    await api('PATCH', `/tasks/${taskId}`, { status });
    loadTasks();
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

// ── Create Task ───────────────────────────────────────────────────────────────

function showCreateForm() {
  document.getElementById('create-form').classList.remove('hidden');
  document.getElementById('new-title').focus();
}

function hideCreateForm() {
  document.getElementById('create-form').classList.add('hidden');
  ['new-title', 'new-owner', 'new-deadline', 'new-project', 'new-notes'].forEach(id => {
    document.getElementById(id).value = '';
  });
}

async function createTask() {
  const title = document.getElementById('new-title').value.trim();
  const owner_name = document.getElementById('new-owner').value.trim();
  const deadline = document.getElementById('new-deadline').value;
  const project = document.getElementById('new-project').value.trim();
  const notes = document.getElementById('new-notes').value.trim();

  if (!title || !deadline) {
    alert('Vui lòng điền tên task và deadline');
    return;
  }

  try {
    await api('POST', '/tasks', { title, owner_name, deadline, project, notes });
    hideCreateForm();
    loadTasks();
  } catch (e) {
    alert('Lỗi tạo task: ' + e.message);
  }
}

// ── Reports ───────────────────────────────────────────────────────────────────

async function loadStandup() {
  document.getElementById('standup-content').textContent = 'Đang tải...';
  try {
    const data = await api('GET', '/reports/standup');
    document.getElementById('standup-content').textContent = data.report;
  } catch (e) {
    document.getElementById('standup-content').textContent = 'Lỗi: ' + e.message;
  }
}

async function loadWeekly() {
  document.getElementById('weekly-content').textContent = 'Đang tải...';
  try {
    const data = await api('GET', '/reports/weekly');
    document.getElementById('weekly-content').textContent = data.report;
  } catch (e) {
    document.getElementById('weekly-content').textContent = 'Lỗi: ' + e.message;
  }
}

// ── Utils ─────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

if (token && currentUser) {
  showApp();
}

// Enter key on login
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('login-password')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') login();
  });
});
