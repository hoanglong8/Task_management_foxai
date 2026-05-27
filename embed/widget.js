/**
 * FOXAI Task Widget — nhúng vào portal nội bộ
 * Cách dùng:
 *   <script src="https://your-server/embed/widget.js"
 *           data-api="https://your-server"
 *           data-token="JWT_TOKEN_HERE"
 *           data-container="#foxai-tasks"></script>
 * Hoặc dùng iframe:
 *   <iframe src="https://your-server/app?embed=1&token=JWT_TOKEN_HERE" width="100%" height="500px"></iframe>
 */
(function () {
  const script = document.currentScript;
  const API = script.getAttribute('data-api') || window.location.origin;
  let TOKEN = script.getAttribute('data-token') || localStorage.getItem('foxai_token');
  const containerId = script.getAttribute('data-container') || '#foxai-widget';

  async function apiFetch(path) {
    const r = await fetch(API + path, {
      headers: TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {},
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }

  function badge(status) {
    const map = { pending: '⏳', in_progress: '🔵', completed: '✅' };
    return map[status] || '📌';
  }

  function createWidget(container) {
    container.innerHTML = `
      <div class="foxai-widget" style="font-family:sans-serif;font-size:14px;max-height:480px;overflow-y:auto;border:1px solid #e0e0e0;border-radius:8px;padding:16px;background:#fff;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <strong>🦊 FOXAI Tasks</strong>
          <button id="foxai-refresh" style="font-size:12px;cursor:pointer;padding:4px 10px;border:1px solid #ccc;border-radius:4px;background:#fff;">🔄</button>
        </div>
        <div id="foxai-task-list">Đang tải...</div>
      </div>`;
    document.getElementById('foxai-refresh').onclick = loadTasks;
    loadTasks();
  }

  async function loadTasks() {
    const el = document.getElementById('foxai-task-list');
    if (!el) return;
    try {
      const tasks = await apiFetch('/tasks?');
      if (!tasks.length) {
        el.innerHTML = '<p style="color:#757575;text-align:center">Không có task nào</p>';
        return;
      }
      const today = new Date().toISOString().split('T')[0];
      el.innerHTML = tasks.slice(0, 15).map(t => {
        const overdue = t.deadline && t.deadline < today && t.status !== 'completed';
        const color = overdue ? '#c62828' : t.status === 'completed' ? '#757575' : '#212121';
        const deadlineStr = t.deadline ? new Date(t.deadline + 'T00:00:00').toLocaleDateString('vi-VN') : '';
        return `
          <div style="padding:8px 0;border-bottom:1px solid #f5f5f5;display:flex;align-items:center;gap:8px;">
            <span>${badge(t.status)}</span>
            <div style="flex:1;">
              <div style="color:${color};font-weight:${t.status !== 'completed' ? 600 : 400}">#${t.id} ${escHtml(t.title)}</div>
              <div style="color:#9e9e9e;font-size:12px;">👤 ${escHtml(t.owner_name || '?')} · 📅 ${deadlineStr}${overdue ? ' <strong style="color:#c62828">Trễ!</strong>' : ''}</div>
            </div>
          </div>`;
      }).join('');
    } catch (e) {
      el.innerHTML = `<p style="color:#c62828">Lỗi tải task: ${e.message}</p>`;
    }
  }

  function escHtml(str) {
    return String(str).replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
  }

  function init() {
    const container = document.querySelector(containerId);
    if (!container) {
      const div = document.createElement('div');
      div.id = 'foxai-widget';
      document.body.appendChild(div);
      createWidget(div);
    } else {
      createWidget(container);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
