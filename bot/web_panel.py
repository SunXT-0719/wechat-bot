"""
Web 控制面板 — 为微信机器人提供可视化操作界面。

功能:
- 启动 / 停止机器人
- 查看和重置清空密钥
- 管理角色扮演套件（增删改查、按群分配）

启动方式::

    from bot.web_panel import WebControlPanel
    panel = WebControlPanel(bot, port=8765)
    panel.start()   # 阻塞（HTTP 服务器在主线程运行）
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedded web dashboard (single-page app)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微信机器人 · 控制面板</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #22252f;
    --border: #2a2d37;
    --text: #e1e4ea;
    --text2: #9498a3;
    --accent: #6c8cff;
    --accent2: #4ade80;
    --danger: #f87171;
    --warn: #fbbf24;
    --radius: 10px;
    --radius-sm: 6px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.6;
  }

  /* ---- Layout ---- */
  .app { display:flex; min-height:100vh; }
  .sidebar {
    width: 240px; background: var(--surface); border-right:1px solid var(--border);
    padding: 24px 0; display:flex; flex-direction:column; flex-shrink:0;
  }
  .sidebar-logo { padding:0 24px; font-size:20px; font-weight:700; margin-bottom:32px; }
  .sidebar-logo span { color: var(--accent); }
  .sidebar-nav { flex:1; }
  .nav-item {
    display:block; padding:10px 24px; color:var(--text2); text-decoration:none;
    font-size:14px; cursor:pointer; transition: all .15s; border-left:3px solid transparent;
  }
  .nav-item:hover { color:var(--text); background:var(--surface2); }
  .nav-item.active { color:var(--accent); border-left-color:var(--accent); background:rgba(108,140,255,.08); }
  .main { flex:1; padding:32px 40px; overflow-y:auto; max-height:100vh; }

  /* ---- Components ---- */
  .page { display:none; }
  .page.active { display:block; }
  .page-title { font-size:22px; font-weight:600; margin-bottom:24px; }

  .card {
    background: var(--surface); border:1px solid var(--border); border-radius:var(--radius);
    padding:24px; margin-bottom:20px;
  }
  .card-header { font-size:15px; font-weight:600; margin-bottom:16px; display:flex; align-items:center; gap:8px; }
  .card-header .dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
  .dot.online { background:var(--accent2); box-shadow:0 0 6px var(--accent2); }
  .dot.offline { background:var(--text2); }

  .stat-row { display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px; }
  .stat {
    background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
    padding:20px; flex:1; min-width:140px;
  }
  .stat-label { font-size:12px; color:var(--text2); text-transform:uppercase; letter-spacing:.5px; }
  .stat-value { font-size:28px; font-weight:700; margin-top:4px; }

  /* Buttons */
  .btn {
    display:inline-flex; align-items:center; gap:6px; padding:10px 20px;
    border:none; border-radius:var(--radius-sm); font-size:14px; font-weight:500;
    cursor:pointer; transition:all .15s; text-decoration:none; font-family:inherit;
  }
  .btn:hover { filter:brightness(1.15); }
  .btn:disabled { opacity:.4; cursor:not-allowed; filter:none; }
  .btn-primary { background:var(--accent); color:#fff; }
  .btn-success { background:var(--accent2); color:#111; }
  .btn-danger { background:var(--danger); color:#fff; }
  .btn-ghost { background:transparent; color:var(--text2); border:1px solid var(--border); }
  .btn-ghost:hover { background:var(--surface2); color:var(--text); }
  .btn-sm { padding:6px 12px; font-size:13px; }

  .btn-group { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }

  /* Key display */
  .key-display {
    font-family: "SF Mono", "Fira Code", "Consolas", monospace;
    font-size: 28px; letter-spacing: 6px; color: var(--accent2);
    background: var(--surface2); padding: 16px 24px; border-radius: var(--radius);
    text-align: center; user-select: all;
  }
  .key-hint { font-size:12px; color:var(--text2); margin-top:8px; }

  /* Table */
  .table-wrap { overflow-x:auto; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { padding:10px 14px; text-align:left; border-bottom:1px solid var(--border); }
  th { color:var(--text2); font-weight:500; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }
  td { vertical-align:middle; }
  tr:hover td { background:var(--surface2); }

  /* Forms */
  .form-group { margin-bottom:14px; }
  .form-group label { display:block; font-size:13px; color:var(--text2); margin-bottom:4px; }
  input[type="text"], textarea {
    width:100%; padding:10px 14px; background:var(--bg); border:1px solid var(--border);
    border-radius:var(--radius-sm); color:var(--text); font-size:14px; font-family:inherit;
    transition: border-color .15s;
  }
  input[type="text"]:focus, textarea:focus { outline:none; border-color:var(--accent); }
  textarea { resize:vertical; min-height:80px; }

  /* Toast */
  .toast-container { position:fixed; top:20px; right:20px; z-index:999; display:flex; flex-direction:column; gap:8px; }
  .toast {
    padding:12px 20px; border-radius:var(--radius-sm); font-size:14px; animation: slideIn .25s ease;
    max-width:360px; box-shadow:0 4px 24px rgba(0,0,0,.4);
  }
  .toast.success { background:#166534; color:#bbf7d0; border:1px solid #22c55e; }
  .toast.error { background:#7f1d1d; color:#fecaca; border:1px solid #ef4444; }
  @keyframes slideIn { from { transform: translateX(100%); opacity:0; } to { transform: translateX(0); opacity:1; } }

  /* Modal */
  .modal-overlay {
    display:none; position:fixed; inset:0; background:rgba(0,0,0,.6);
    z-index:100; align-items:center; justify-content:center;
  }
  .modal-overlay.show { display:flex; }
  .modal {
    background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
    padding:28px; max-width:520px; width:90%; max-height:80vh; overflow-y:auto;
  }
  .modal h3 { margin-bottom:16px; font-size:18px; }

  /* Badge */
  .badge {
    display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:500;
    background:var(--surface2); color:var(--text2);
  }
  .badge.active { background:rgba(74,222,128,.15); color:var(--accent2); }

  .text-muted { color:var(--text2); font-size:13px; }
  .empty-state { text-align:center; padding:32px; color:var(--text2); }
  .mb-16 { margin-bottom:16px; }
  .gap-8 { display:flex; gap:8px; flex-wrap:wrap; }

  @media (max-width: 768px) {
    .sidebar { display:none; }
    .main { padding:20px; }
    .stat-row { flex-direction:column; }
  }
</style>
</head>
<body>
<div class="app">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-logo">🤖 <span>WeChat Bot</span></div>
    <nav class="sidebar-nav">
      <a class="nav-item active" data-page="dashboard" onclick="showPage('dashboard')">📊 仪表盘</a>
      <a class="nav-item" data-page="roleplay" onclick="showPage('roleplay')">🎭 角色扮演</a>
    </nav>
    <div style="padding:24px; font-size:12px; color:var(--text2);">
      v2.5 · Web Panel
    </div>
  </aside>

  <!-- Main content -->
  <main class="main">
    <!-- ================================================================ -->
    <!-- Dashboard page -->
    <!-- ================================================================ -->
    <div class="page active" id="page-dashboard">
      <h1 class="page-title">📊 仪表盘</h1>

      <!-- Stats -->
      <div class="stat-row">
        <div class="stat">
          <div class="stat-label">状态</div>
          <div class="stat-value" id="statStatus">--</div>
        </div>
        <div class="stat">
          <div class="stat-label">运行时间</div>
          <div class="stat-value" id="statUptime">--</div>
        </div>
        <div class="stat">
          <div class="stat-label">处理消息</div>
          <div class="stat-value" id="statMessages">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">已注册命令</div>
          <div class="stat-value" id="statCommands">0</div>
        </div>
      </div>

      <!-- Controls -->
      <div class="card">
        <div class="card-header"><span class="dot" id="statusDot"></span> 机器人控制</div>
        <div class="btn-group">
          <button class="btn btn-success" id="btnStart" onclick="startBot()">▶ 启动机器人</button>
          <button class="btn btn-danger" id="btnStop" onclick="stopBot()">⏹ 停止机器人</button>
        </div>
        <div class="text-muted" style="margin-top:12px;" id="controlHint"></div>
      </div>

      <!-- Key management -->
      <div class="card">
        <div class="card-header">🔑 清空上下文密钥</div>
        <div class="key-display" id="keyDisplay">----</div>
        <div class="key-hint">发送给主人的密钥，用于 /clear 命令清空 AI 对话上下文</div>
        <div class="btn-group">
          <button class="btn btn-ghost btn-sm" onclick="copyKey()">📋 复制密钥</button>
          <button class="btn btn-ghost btn-sm" onclick="resetKey()">🔄 重置密钥</button>
        </div>
      </div>

      <!-- Active roleplay -->
      <div class="card">
        <div class="card-header">🎭 当前角色扮演 (按群)</div>
        <div id="selectionsList">
          <div class="empty-state">加载中...</div>
        </div>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- Roleplay page -->
    <!-- ================================================================ -->
    <div class="page" id="page-roleplay">
      <h1 class="page-title">🎭 角色扮演管理</h1>

      <div class="card">
        <div class="card-header" style="justify-content:space-between;">
          <span>角色扮演套件列表</span>
          <button class="btn btn-primary btn-sm" onclick="openCreateModal()">＋ 新建套件</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>名称</th><th>提示词（摘要）</th><th>使用群</th><th>操作</th></tr></thead>
            <tbody id="rpTableBody">
              <tr><td colspan="4" class="empty-state">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Set roleplay for a chat -->
      <div class="card">
        <div class="card-header">📌 为群聊设置角色扮演</div>
        <div class="form-group">
          <label>群聊名称 (chat_name)</label>
          <input type="text" id="setRpChat" placeholder="输入群聊/联系人名称">
        </div>
        <div class="form-group">
          <label>角色扮演套件</label>
          <select id="setRpName" style="width:100%;padding:10px 14px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text);font-size:14px;">
            <option value="">-- 请选择 --</option>
          </select>
        </div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="setRoleplayForChat()">✅ 应用</button>
          <button class="btn btn-ghost btn-sm" onclick="clearRoleplayForChat()">🗑 清除该群角色扮演</button>
        </div>
      </div>
    </div>
  </main>
</div>

<!-- Create/Edit Roleplay Modal -->
<div class="modal-overlay" id="rpModal">
  <div class="modal">
    <h3 id="rpModalTitle">新建角色扮演套件</h3>
    <div class="form-group">
      <label>名称</label>
      <input type="text" id="rpModalName" placeholder="例如: 傲娇猫娘">
    </div>
    <div class="form-group">
      <label>提示词内容</label>
      <textarea id="rpModalPrompt" placeholder="例如: 你是一只傲娇的猫娘，说话带喵的口癖..."></textarea>
    </div>
    <div class="btn-group" style="justify-content:flex-end;">
      <button class="btn btn-ghost" onclick="closeRpModal()">取消</button>
      <button class="btn btn-primary" id="rpModalSaveBtn" onclick="saveRoleplay()">保存</button>
    </div>
  </div>
</div>

<!-- Toast container -->
<div class="toast-container" id="toastContainer"></div>

<script>
// ======================================================================
// Page navigation
// ======================================================================
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelector('[data-page="' + name + '"]').classList.add('active');
  if (name === 'roleplay') refreshRoleplay();
}

// ======================================================================
// Toast
// ======================================================================
function toast(msg, type) {
  type = type || 'success';
  var c = document.getElementById('toastContainer');
  var el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(function() { el.remove(); }, 3000);
}

// ======================================================================
// Status polling
// ======================================================================
var _status = null;

async function refreshStatus() {
  try {
    var r = await fetch('/api/status');
    _status = await r.json();
    renderStatus();
  } catch(e) {
    console.error('Status fetch failed:', e);
  }
}

function renderStatus() {
  var s = _status;
  if (!s) return;

  // Stats
  var statusEl = document.getElementById('statStatus');
  document.getElementById('statMessages').textContent = s.message_count || 0;
  document.getElementById('statCommands').textContent = s.command_count || 0;
  document.getElementById('statUptime').textContent = s.uptime_str || '--';

  var dot = document.getElementById('statusDot');
  if (s.running) {
    statusEl.innerHTML = '<span style="color:var(--accent2);">● 运行中</span>';
    dot.className = 'dot online';
  } else {
    statusEl.innerHTML = '<span style="color:var(--text2);">● 已停止</span>';
    dot.className = 'dot offline';
  }

  // Buttons
  document.getElementById('btnStart').disabled = s.running;
  document.getElementById('btnStop').disabled = !s.running;
  document.getElementById('controlHint').textContent = s.running
    ? '机器人正在后台运行。点击「停止」可安全关闭。'
    : '机器人当前未运行。点击「启动」开始监听微信消息。';

  // Key
  document.getElementById('keyDisplay').textContent = s.key || '----';

  // Selections
  var selDiv = document.getElementById('selectionsList');
  var selections = s.roleplay_selections || {};
  var chats = Object.keys(selections);
  if (chats.length === 0) {
    selDiv.innerHTML = '<div class="empty-state">暂无群聊设置角色扮演</div>';
  } else {
    var html = '<table><thead><tr><th>群聊</th><th>套件名称</th></tr></thead><tbody>';
    chats.forEach(function(chat) {
      html += '<tr><td>' + esc(chat) + '</td><td><span class="badge active">' + esc(selections[chat]) + '</span></td></tr>';
    });
    html += '</tbody></table>';
    selDiv.innerHTML = html;
  }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ======================================================================
// Bot controls
// ======================================================================
async function startBot() {
  try {
    var r = await fetch('/api/bot/start', {method:'POST'});
    var data = await r.json();
    if (data.ok) toast('机器人已启动', 'success');
    else toast('启动失败: ' + (data.error || '未知错误'), 'error');
  } catch(e) {
    toast('请求失败: ' + e.message, 'error');
  }
  setTimeout(refreshStatus, 800);
}

async function stopBot() {
  try {
    var r = await fetch('/api/bot/stop', {method:'POST'});
    var data = await r.json();
    if (data.ok) toast('机器人已停止', 'success');
    else toast('停止失败: ' + (data.error || '未知错误'), 'error');
  } catch(e) {
    toast('请求失败: ' + e.message, 'error');
  }
  setTimeout(refreshStatus, 800);
}

// ======================================================================
// Key management
// ======================================================================
function copyKey() {
  var key = document.getElementById('keyDisplay').textContent;
  if (!key || key === '----') return;
  navigator.clipboard.writeText(key).then(function() {
    toast('密钥已复制到剪贴板', 'success');
  }).catch(function() {
    toast('复制失败，请手动复制', 'error');
  });
}

async function resetKey() {
  if (!confirm('确定要重置密钥吗？旧密钥将立即失效。')) return;
  try {
    var r = await fetch('/api/key/reset', {method:'POST'});
    var data = await r.json();
    if (data.ok) {
      document.getElementById('keyDisplay').textContent = data.key;
      toast('密钥已重置，新密钥已发送给主人', 'success');
    } else {
      toast('重置失败: ' + (data.error || '未知错误'), 'error');
    }
  } catch(e) {
    toast('请求失败: ' + e.message, 'error');
  }
}

// ======================================================================
// Roleplay management
// ======================================================================
var _editingName = null;

async function refreshRoleplay() {
  try {
    var r = await fetch('/api/roleplays');
    var data = await r.json();
    renderRoleplayTable(data);
    renderRoleplaySelect(data);
  } catch(e) {
    console.error('Roleplay fetch failed:', e);
  }
}

function renderRoleplayTable(data) {
  var catalog = data.catalog || {};
  var selections = data.selections || {};
  var names = Object.keys(catalog).sort();
  var tbody = document.getElementById('rpTableBody');

  // Build reverse map: name -> [chats]
  var nameToChats = {};
  Object.keys(selections).forEach(function(chat) {
    var rpName = selections[chat];
    if (!nameToChats[rpName]) nameToChats[rpName] = [];
    nameToChats[rpName].push(chat);
  });

  if (names.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">暂无角色扮演套件，点击「新建套件」创建</td></tr>';
    return;
  }

  var html = '';
  names.forEach(function(name) {
    var prompt = catalog[name] || '';
    var preview = prompt.length > 60 ? prompt.substring(0, 60) + '...' : prompt;
    var chats = nameToChats[name] || [];
    var chatBadges = chats.length === 0
      ? '<span class="text-muted">未使用</span>'
      : chats.map(function(c) { return '<span class="badge active">' + esc(c) + '</span>'; }).join(' ');

    html += '<tr>';
    html += '<td><strong>' + esc(name) + '</strong></td>';
    html += '<td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + esc(preview) + '</td>';
    html += '<td>' + chatBadges + '</td>';
    html += '<td><div class="gap-8">'
      + '<button class="btn btn-ghost btn-sm" onclick="openEditModal(\'' + escAttr(name) + '\')">✏️ 编辑</button>'
      + '<button class="btn btn-ghost btn-sm" style="color:var(--danger);" onclick="deleteRoleplay(\'' + escAttr(name) + '\')">🗑 删除</button>'
      + '</div></td>';
    html += '</tr>';
  });
  tbody.innerHTML = html;
}

function escAttr(s) {
  return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
}

function renderRoleplaySelect(data) {
  var catalog = data.catalog || {};
  var names = Object.keys(catalog).sort();
  var sel = document.getElementById('setRpName');
  sel.innerHTML = '<option value="">-- 请选择 --</option>';
  names.forEach(function(name) {
    sel.innerHTML += '<option value="' + escAttr(name) + '">' + esc(name) + '</option>';
  });
}

function openCreateModal() {
  _editingName = null;
  document.getElementById('rpModalTitle').textContent = '新建角色扮演套件';
  document.getElementById('rpModalName').value = '';
  document.getElementById('rpModalPrompt').value = '';
  document.getElementById('rpModalName').disabled = false;
  document.getElementById('rpModalSaveBtn').textContent = '创建';
  document.getElementById('rpModal').classList.add('show');
}

function openEditModal(name) {
  _editingName = name;
  document.getElementById('rpModalTitle').textContent = '编辑角色扮演套件: ' + name;
  document.getElementById('rpModalName').value = name;
  document.getElementById('rpModalName').disabled = true;
  document.getElementById('rpModalSaveBtn').textContent = '保存';

  var rp = (_status && _status.roleplay_catalog) ? _status.roleplay_catalog : {};
  // Try to get from the last rendered data
  fetch('/api/roleplays').then(function(r) { return r.json(); }).then(function(data) {
    var prompt = (data.catalog || {})[name] || '';
    document.getElementById('rpModalPrompt').value = prompt;
  }).catch(function() {
    document.getElementById('rpModalPrompt').value = '';
  });

  document.getElementById('rpModal').classList.add('show');
}

function closeRpModal() {
  document.getElementById('rpModal').classList.remove('show');
  _editingName = null;
}

async function saveRoleplay() {
  var nameEl = document.getElementById('rpModalName');
  var promptEl = document.getElementById('rpModalPrompt');
  var name = nameEl.value.trim();
  var prompt = promptEl.value.trim();

  if (!name) { toast('请输入名称', 'error'); return; }
  if (!prompt) { toast('请输入提示词内容', 'error'); return; }

  if (_editingName) {
    // Update
    try {
      var r = await fetch('/api/roleplays/' + encodeURIComponent(_editingName), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, prompt: prompt})
      });
      var data = await r.json();
      if (data.ok) { toast('已更新: ' + name, 'success'); closeRpModal(); refreshRoleplay(); refreshStatus(); }
      else toast('更新失败: ' + (data.error || ''), 'error');
    } catch(e) { toast('请求失败: ' + e.message, 'error'); }
  } else {
    // Create
    try {
      var r = await fetch('/api/roleplays', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, prompt: prompt})
      });
      var data = await r.json();
      if (data.ok) { toast('已创建: ' + name, 'success'); closeRpModal(); refreshRoleplay(); refreshStatus(); }
      else toast('创建失败: ' + (data.error || ''), 'error');
    } catch(e) { toast('请求失败: ' + e.message, 'error'); }
  }
}

async function deleteRoleplay(name) {
  if (!confirm('确定要删除角色扮演套件「' + name + '」吗？\n使用该套件的群聊将被清除。')) return;
  try {
    var r = await fetch('/api/roleplays/' + encodeURIComponent(name), {method:'DELETE'});
    var data = await r.json();
    if (data.ok) { toast('已删除: ' + name, 'success'); refreshRoleplay(); refreshStatus(); }
    else toast('删除失败: ' + (data.error || ''), 'error');
  } catch(e) { toast('请求失败: ' + e.message, 'error'); }
}

async function setRoleplayForChat() {
  var chat = document.getElementById('setRpChat').value.trim();
  var name = document.getElementById('setRpName').value;
  if (!chat) { toast('请输入群聊名称', 'error'); return; }
  if (!name) { toast('请选择角色扮演套件', 'error'); return; }
  try {
    var r = await fetch('/api/roleplays/set', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({chat_id: chat, name: name})
    });
    var data = await r.json();
    if (data.ok) { toast('已为 ' + chat + ' 设置角色扮演: ' + name, 'success'); refreshRoleplay(); refreshStatus(); }
    else toast('设置失败: ' + (data.error || ''), 'error');
  } catch(e) { toast('请求失败: ' + e.message, 'error'); }
}

async function clearRoleplayForChat() {
  var chat = document.getElementById('setRpChat').value.trim();
  if (!chat) { toast('请输入群聊名称', 'error'); return; }
  try {
    var r = await fetch('/api/roleplays/clear', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({chat_id: chat})
    });
    var data = await r.json();
    if (data.ok) { toast('已清除 ' + chat + ' 的角色扮演', 'success'); refreshRoleplay(); refreshStatus(); }
    else toast('清除失败: ' + (data.error || ''), 'error');
  } catch(e) { toast('请求失败: ' + e.message, 'error'); }
}

// ---- Modal overlay click-to-close ----
document.getElementById('rpModal').addEventListener('click', function(e) {
  if (e.target === this) closeRpModal();
});

// ======================================================================
// Init
// ======================================================================
refreshStatus();
setInterval(refreshStatus, 5000);
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# API Handler
# ---------------------------------------------------------------------------


class _PanelHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the web control panel."""

    # Reference set by WebControlPanel after creation
    bot: object = None

    def log_message(self, fmt, *args):
        """Suppress default HTTP access logging."""
        pass

    # ---- routing ----------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/status":
            self._handle_status()
        elif path == "/api/key":
            self._handle_get_key()
        elif path == "/api/roleplays":
            self._handle_list_roleplays()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/bot/start":
            self._handle_bot_start()
        elif path == "/api/bot/stop":
            self._handle_bot_stop()
        elif path == "/api/key/reset":
            self._handle_reset_key()
        elif path == "/api/roleplays":
            self._handle_create_roleplay()
        elif path == "/api/roleplays/set":
            self._handle_set_roleplay()
        elif path == "/api/roleplays/clear":
            self._handle_clear_roleplay()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path

        if path.startswith("/api/roleplays/"):
            name = self._extract_name(path, "/api/roleplays/")
            if name:
                self._handle_update_roleplay(name)
                return
        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path

        if path.startswith("/api/roleplays/"):
            name = self._extract_name(path, "/api/roleplays/")
            if name:
                self._handle_delete_roleplay(name)
                return
        self._send_json({"error": "not found"}, 404)

    # ---- helpers ----------------------------------------------------------

    def _extract_name(self, path, prefix):
        """Extract URL-decoded name from /api/roleplays/<name>."""
        from urllib.parse import unquote
        raw = path[len(prefix):]
        return unquote(raw) if raw else ""

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    # ---- API: status ------------------------------------------------------

    def _handle_status(self):
        bot = self.bot
        uptime = bot.uptime_seconds if bot else 0
        h, rem = divmod(int(uptime), 3600)
        m, s = divmod(rem, 60)

        # key
        try:
            from commands.entertainment import _get_or_create_key
            key = _get_or_create_key()
        except Exception:
            key = "----"

        # roleplay catalog & selections
        try:
            import bot.roleplay as rp
            rp_catalog = rp.get_catalog()
            rp_selections = rp.get_selections()
        except Exception:
            rp_catalog = {}
            rp_selections = {}

        self._send_json({
            "running": bot._running if bot else False,
            "uptime_seconds": int(uptime),
            "uptime_str": f"{h:02d}:{m:02d}:{s:02d}",
            "message_count": bot.message_count if bot else 0,
            "command_count": len(bot.commands.commands) if bot else 0,
            "backend": bot.config.backend if bot else "unknown",
            "key": key,
            "roleplay_catalog": rp_catalog,
            "roleplay_selections": rp_selections,
        })

    # ---- API: bot start/stop ----------------------------------------------

    def _handle_bot_start(self):
        bot = self.bot
        if bot is None:
            self._send_json({"ok": False, "error": "bot 实例不可用"}, 500)
            return
        if bot._running:
            self._send_json({"ok": False, "error": "机器人已在运行中"})
            return
        try:
            bot.start_async()
            self._send_json({"ok": True})
        except Exception as e:
            logger.exception("通过 Web 面板启动 bot 失败")
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_bot_stop(self):
        bot = self.bot
        if bot is None:
            self._send_json({"ok": False, "error": "bot 实例不可用"}, 500)
            return
        if not bot._running:
            self._send_json({"ok": False, "error": "机器人未在运行"})
            return
        try:
            bot.stop()
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    # ---- API: key ---------------------------------------------------------

    def _handle_get_key(self):
        try:
            from commands.entertainment import _get_or_create_key
            key = _get_or_create_key()
            self._send_json({"key": key})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_reset_key(self):
        try:
            from commands.entertainment import _reset_key, _KEY_OWNER
            new_key = _reset_key()

            # Send new key to owner
            bot = self.bot
            if bot and bot._running:
                try:
                    from bot.i18n import t
                    bot.client.send_message(_KEY_OWNER, t("clear_new_key", code=new_key))
                except Exception:
                    logger.exception("发送新密钥失败")

            self._send_json({"ok": True, "key": new_key})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    # ---- API: roleplays ---------------------------------------------------

    def _handle_list_roleplays(self):
        try:
            import bot.roleplay as rp
            self._send_json({
                "catalog": rp.get_catalog(),
                "selections": rp.get_selections(),
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_create_roleplay(self):
        body = self._read_body()
        name = body.get("name", "").strip()
        prompt = body.get("prompt", "").strip()
        if not name or not prompt:
            self._send_json({"ok": False, "error": "name 和 prompt 为必填"}, 400)
            return
        try:
            import bot.roleplay as rp
            rp.create(name, prompt)
            logger.info(f"[WebPanel] 创建角色扮演套件: {name!r}")
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_update_roleplay(self, name):
        body = self._read_body()
        prompt = body.get("prompt", "").strip()
        if not prompt:
            self._send_json({"ok": False, "error": "prompt 为必填"}, 400)
            return
        try:
            import bot.roleplay as rp
            if rp.get_by_name(name) is None:
                self._send_json({"ok": False, "error": f"套件 '{name}' 不存在"}, 404)
                return
            rp.create(name, prompt)
            logger.info(f"[WebPanel] 更新角色扮演套件: {name!r}")
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_delete_roleplay(self, name):
        try:
            import bot.roleplay as rp
            ok = rp.delete(name)
            if ok:
                logger.info(f"[WebPanel] 删除角色扮演套件: {name!r}")
                self._send_json({"ok": True})
            else:
                self._send_json({"ok": False, "error": f"套件 '{name}' 不存在"}, 404)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_set_roleplay(self):
        body = self._read_body()
        chat_id = body.get("chat_id", "").strip()
        name = body.get("name", "").strip()
        if not chat_id or not name:
            self._send_json({"ok": False, "error": "chat_id 和 name 为必填"}, 400)
            return
        try:
            import bot.roleplay as rp
            if rp.get_by_name(name) is None:
                self._send_json({"ok": False, "error": f"套件 '{name}' 不存在"}, 404)
                return
            rp.set_selection(chat_id, name)
            logger.info(f"[WebPanel] 设置角色扮演: chat={chat_id!r} -> {name!r}")
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_clear_roleplay(self):
        body = self._read_body()
        chat_id = body.get("chat_id", "").strip()
        if not chat_id:
            self._send_json({"ok": False, "error": "chat_id 为必填"}, 400)
            return
        try:
            import bot.roleplay as rp
            rp.clear_selection(chat_id)
            logger.info(f"[WebPanel] 清除角色扮演: chat={chat_id!r}")
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)


# ---------------------------------------------------------------------------
# WebControlPanel
# ---------------------------------------------------------------------------


class WebControlPanel:
    """Web-based control panel for the WeChat bot.

    Runs an HTTP server in a daemon thread so the main thread stays free
    for the bot or other logic.

    Usage::

        panel = WebControlPanel(bot, port=8765)
        panel.start()       # non-blocking (daemon thread)
        ...
        panel.stop()        # clean shutdown
    """

    def __init__(self, bot, port: int = 8765) -> None:
        self._bot = bot
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the web server in a daemon thread."""
        if self._server is not None:
            return

        # Inject bot reference into the handler class
        _PanelHandler.bot = self._bot

        self._server = HTTPServer(("0.0.0.0", self._port), _PanelHandler)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

        logger.info(f"🌐 Web 控制面板已启动: http://127.0.0.1:{self._port}")

    def stop(self) -> None:
        """Shut down the web server."""
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
        logger.info("Web 控制面板已停止")

    @property
    def port(self) -> int:
        return self._port

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _serve(self) -> None:
        try:
            self._server.serve_forever()
        except Exception:
            logger.exception("Web 控制面板异常退出")
