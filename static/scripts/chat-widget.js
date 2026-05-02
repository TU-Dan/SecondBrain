/**
 * Brain Chat Widget — multi-session, NDJSON event stream
 */
(function () {
  if (window.__brainChatLoaded) return;
  window.__brainChatLoaded = true;

  // ── 样式 ──────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #brain-bubble {
      position: fixed; z-index: 9999;
      display: none; align-items: center; gap: 6px;
      background: var(--accent, #4a6741); color: #fff;
      font-size: 12px; font-family: 'DM Sans', sans-serif;
      padding: 5px 11px 5px 8px; border-radius: 20px;
      cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,.25);
      user-select: none; white-space: nowrap;
      transition: opacity .15s, transform .15s;
      pointer-events: auto;
    }
    #brain-bubble:hover { opacity: .88; transform: scale(1.04); }
    #brain-bubble svg { width:13px; height:13px; flex-shrink:0; }

    #brain-panel {
      position: fixed; top:0; right:0; width:390px; max-width:93vw;
      height:100vh; z-index:9998;
      display:flex; flex-direction:column;
      background: var(--bg, #f0f0e8);
      border-left: 1px solid var(--border, rgba(0,0,0,.12));
      box-shadow: -8px 0 48px rgba(0,0,0,.18);
      transform: translateX(100%);
      transition: transform .28s cubic-bezier(.4,0,.2,1);
      font-family: 'DM Sans','PingFang SC',sans-serif;
    }
    [data-theme="dark"] #brain-panel { background: #1e2718; }
    #brain-panel.open { transform: translateX(0); }

    #brain-overlay {
      display:none; position:fixed; inset:0; z-index:9990;
    }
    #brain-overlay.open { display:block; }

    /* Header */
    #brain-header {
      display:flex; align-items:center; justify-content:space-between;
      padding:13px 16px; border-bottom:1px solid var(--border,rgba(0,0,0,.12));
      flex-shrink:0;
      background: var(--bg, #f0f0e8);
    }
    [data-theme="dark"] #brain-header { background: #1e2718; }
    .brain-h-title {
      font-size:13.5px; font-weight:600; color:var(--text,#1a1a14);
      display:flex; align-items:center; gap:7px;
    }
    .brain-h-title svg { width:15px; height:15px; color:var(--accent,#4a6741); }
    .brain-h-btn {
      background:none; border:none; cursor:pointer;
      color:var(--text-muted,#888); padding:4px 6px;
      border-radius:6px; display:flex; align-items:center;
      transition:color .15s, background .15s; font-size:12px;
    }
    .brain-h-btn:hover { color:var(--text,#1a1a14); background:var(--surface-2,rgba(0,0,0,.05)); }
    .brain-h-btn svg { width:15px; height:15px; }
    .brain-h-btn.active { color:var(--accent,#4a6741); }

    /* Sessions view */
    #brain-sessions-view {
      display:none; flex-direction:column; flex:1; overflow:hidden;
    }
    #brain-sessions-view.visible { display:flex; }
    #brain-new-chat-btn {
      margin:12px 14px 8px;
      display:flex; align-items:center; gap:7px;
      padding:9px 13px; border-radius:10px; border:none; cursor:pointer;
      background:var(--accent,#4a6741); color:#fff;
      font-size:13px; font-weight:500; font-family:inherit;
      transition:opacity .15s;
    }
    #brain-new-chat-btn:hover { opacity:.85; }
    #brain-new-chat-btn svg { width:14px; height:14px; }
    #brain-sessions-list {
      flex:1; overflow-y:auto; padding:4px 8px 12px;
      display:flex; flex-direction:column; gap:2px;
    }
    .bsess-item {
      display:flex; align-items:center; gap:8px;
      padding:9px 10px; border-radius:9px; cursor:pointer;
      transition:background .12s; position:relative;
    }
    .bsess-item:hover { background:var(--surface-2,rgba(0,0,0,.05)); }
    .bsess-item.active { background:var(--surface-2,rgba(0,0,0,.07)); }
    [data-theme="dark"] .bsess-item:hover,
    [data-theme="dark"] .bsess-item.active { background:rgba(255,255,255,.07); }
    .bsess-body { flex:1; overflow:hidden; }
    .bsess-title {
      font-size:13px; color:var(--text,#1a1a14);
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
      font-weight:500;
    }
    .bsess-item.active .bsess-title { color:var(--accent,#4a6741); }
    .bsess-meta {
      font-size:11px; color:var(--text-muted,#999); margin-top:2px;
    }
    .bsess-del {
      background:none; border:none; cursor:pointer;
      color:var(--text-muted,#bbb); padding:3px 5px;
      border-radius:5px; font-size:14px; line-height:1;
      opacity:0; transition:opacity .12s, color .12s;
      flex-shrink:0;
    }
    .bsess-item:hover .bsess-del { opacity:1; }
    .bsess-del:hover { color:#e05a5a; }
    .bsess-empty {
      text-align:center; padding:32px 16px;
      color:var(--text-muted,#bbb); font-size:13px;
    }

    /* Messages */
    #brain-msgs {
      flex:1; overflow-y:auto; padding:16px;
      display:flex; flex-direction:column; gap:14px;
    }
    .bmsg-user {
      align-self:flex-end; max-width:86%;
      background:var(--accent,#4a6741); color:#fff;
      padding:9px 13px; border-radius:14px 14px 3px 14px;
      font-size:13.5px; line-height:1.6; white-space:pre-wrap; word-break:break-word;
    }
    .bmsg-quote {
      background:rgba(255,255,255,.18); border-left:2px solid rgba(255,255,255,.5);
      border-radius:0 6px 6px 0; padding:5px 10px;
      font-size:11.5px; opacity:.85; font-style:italic;
      margin-bottom:5px; line-height:1.45;
    }
    .bmsg-assistant {
      align-self:flex-start; color:var(--text,#1a1a14);
      font-size:13.5px; line-height:1.65; max-width:100%;
    }
    .bmsg-assistant p { margin:0 0 8px; }
    .bmsg-assistant p:last-child { margin-bottom:0; }
    .bmsg-assistant strong { font-weight:600; }
    .bmsg-assistant em { font-style:italic; }
    .bmsg-assistant ul,.bmsg-assistant ol { margin:5px 0 5px 16px; }
    .bmsg-assistant li { margin-bottom:3px; }
    .bmsg-assistant h1,.bmsg-assistant h2,.bmsg-assistant h3 {
      font-size:14px; font-weight:700; margin:12px 0 4px;
    }
    .bmsg-assistant code {
      background:var(--surface-2,rgba(0,0,0,.07));
      padding:1px 5px; border-radius:4px; font-size:12px;
    }
    .bmsg-assistant hr { border:none; border-top:1px solid var(--border,rgba(0,0,0,.1)); margin:8px 0; }
    .bmsg-assistant blockquote {
      border-left:3px solid var(--accent,#4a6741);
      margin:6px 0; padding:4px 10px;
      color:var(--text-muted,#777); font-style:italic;
    }

    /* Thinking bar */
    .brain-thinking {
      display:flex; align-items:center; gap:8px;
      font-size:12px; color:var(--text-muted,#888);
      padding:4px 0; animation: brain-fade-in .2s ease;
    }
    .brain-thinking-dots { display:flex; gap:3px; }
    .brain-thinking-dots span {
      width:5px; height:5px; background:var(--accent,#4a6741);
      border-radius:50%; opacity:.5;
      animation: brain-dot 1.2s infinite;
    }
    .brain-thinking-dots span:nth-child(2) { animation-delay:.2s; }
    .brain-thinking-dots span:nth-child(3) { animation-delay:.4s; }
    @keyframes brain-dot {
      0%,80%,100% { transform:translateY(0); opacity:.4; }
      40% { transform:translateY(-4px); opacity:1; }
    }
    @keyframes brain-fade-in { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }

    /* Tool call block */
    .brain-tool {
      border:1px solid var(--border,rgba(0,0,0,.1));
      border-radius:10px; overflow:hidden;
      font-size:12px; animation: brain-fade-in .2s ease;
    }
    .brain-tool-header {
      display:flex; align-items:center; gap:6px;
      padding:7px 11px; cursor:pointer;
      background:var(--surface-2,rgba(0,0,0,.04));
      user-select:none;
      transition:background .15s;
    }
    .brain-tool-header:hover { background:var(--surface-2,rgba(0,0,0,.07)); }
    .brain-tool-icon { font-size:13px; }
    .brain-tool-name { font-weight:600; color:var(--text,#1a1a14); flex:1; }
    .brain-tool-args { color:var(--text-muted,#999); font-size:11px; max-width:160px; overflow:hidden; white-space:nowrap; }
    .brain-tool-chevron { color:var(--text-muted,#bbb); font-size:10px; transition:transform .2s; }
    .brain-tool.open .brain-tool-chevron { transform:rotate(180deg); }
    .brain-tool-body {
      display:none; padding:10px 12px;
      color:var(--text-muted,#666); line-height:1.55;
      border-top:1px solid var(--border,rgba(0,0,0,.08));
      white-space:pre-wrap; word-break:break-word;
      max-height:220px; overflow-y:auto;
    }
    .brain-tool.open .brain-tool-body { display:block; }

    /* Footer */
    #brain-footer {
      padding:11px 13px; border-top:1px solid var(--border,rgba(0,0,0,.12));
      display:flex; gap:8px; align-items:flex-end; flex-shrink:0;
      background: var(--bg, #f0f0e8);
    }
    [data-theme="dark"] #brain-footer { background: #1e2718; }
    #brain-input {
      flex:1; resize:none; border:1px solid var(--border,rgba(0,0,0,.12));
      border-radius:10px; padding:9px 12px;
      font-size:13.5px; font-family:inherit;
      background:var(--bg,#f0f0e8); color:var(--text,#1a1a14);
      outline:none; min-height:40px; max-height:120px; line-height:1.5;
      transition:border-color .15s;
    }
    #brain-input:focus { border-color:var(--accent,#4a6741); }
    #brain-input::placeholder { color:var(--text-muted,#bbb); }
    #brain-send {
      background:var(--accent,#4a6741); border:none; border-radius:10px;
      width:36px; height:36px; flex-shrink:0; cursor:pointer;
      display:flex; align-items:center; justify-content:center; color:#fff;
      transition:opacity .15s;
    }
    #brain-send:hover { opacity:.85; }
    #brain-send:disabled { opacity:.35; cursor:not-allowed; }
    #brain-send svg { width:14px; height:14px; }

    /* FAB */
    #brain-fab {
      position:fixed; bottom:24px; right:24px; z-index:9997;
      width:46px; height:46px; border-radius:50%;
      background:var(--accent,#4a6741); border:none; cursor:pointer;
      display:flex; align-items:center; justify-content:center; color:#fff;
      box-shadow:0 4px 20px rgba(0,0,0,.2);
      transition:opacity .15s, transform .15s;
    }
    #brain-fab:hover { opacity:.88; transform:scale(1.06); }
    #brain-fab svg { width:20px; height:20px; }

    #brain-resize-grip {
      position:absolute; left:0; top:0; bottom:0; width:5px;
      cursor:col-resize; background:transparent;
      transition:background .15s;
    }
    #brain-resize-grip:hover,
    #brain-resize-grip.dragging { background:var(--accent,#4a6741); }

    #brain-panel.inline {
      position:relative; inset:auto; width:100%; max-width:none;
      height:100%; z-index:auto; transform:none; box-shadow:none;
      border-left:none; background:transparent;
    }
    #brain-panel.inline.open { transform:none; }
    #brain-panel.inline #brain-header {
      padding:9px 11px; background:transparent;
    }
    #brain-panel.inline #brain-footer {
      padding:10px; background:transparent;
    }
    #brain-panel.inline #brain-msgs { padding:12px; }
    #brain-panel.inline .brain-h-title {
      min-width:0; font-size:12.5px; text-transform:uppercase;
      letter-spacing:.7px; color:var(--text-muted,#888);
    }
    #brain-panel.inline .brain-h-title span {
      display:block; min-width:0; overflow:hidden;
      white-space:nowrap; text-overflow:ellipsis;
    }
    #brain-panel.inline .bmsg-user { max-width:92%; }
    #brain-panel.inline .brain-empty {
      margin:auto; max-width:300px; text-align:center;
      color:var(--text-muted,#888); font-size:13px; line-height:1.7;
    }
    #brain-panel.inline #brain-resize-grip { display:none; }
  `;
  document.head.appendChild(style);

  // ── DOM ───────────────────────────────────────────────────────────────────
  const inlineMount = document.getElementById('brain-inline-panel');
  const panelMarkup = `
    <div id="brain-panel"${inlineMount ? ' class="inline"' : ''}>
      <div id="brain-resize-grip"></div>
      <div id="brain-header">
        <div class="brain-h-title">
          <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span>问大脑</span>
        </div>
        <div style="display:flex;align-items:center;gap:4px">
          <button id="brain-sessions-btn" class="brain-h-btn" title="历史对话">
            <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>
              <line x1="8" y1="18" x2="21" y2="18"/>
              <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/>
              <line x1="3" y1="18" x2="3.01" y2="18"/>
            </svg>
          </button>
          <button id="brain-new-btn" class="brain-h-btn" title="新对话">
            <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button id="brain-close" class="brain-h-btn" title="${inlineMount ? '折叠' : '关闭'}">
            <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Sessions list view -->
      <div id="brain-sessions-view">
        <button id="brain-new-chat-btn">
          <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          新对话
        </button>
        <div id="brain-sessions-list"></div>
      </div>

      <!-- Chat view -->
      <div id="brain-msgs"></div>
      <div id="brain-footer">
        <textarea id="brain-input" placeholder="问大脑任何问题… (Enter 发送)" rows="1"></textarea>
        <button id="brain-send">
          <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', `
    <div id="brain-bubble">
      <svg fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      问大脑
    </div>

    <div id="brain-overlay"></div>

    <button id="brain-fab" title="打开大脑对话">
      <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    </button>
  `);
  if (inlineMount) {
    inlineMount.innerHTML = panelMarkup;
  } else {
    document.body.insertAdjacentHTML('beforeend', panelMarkup);
  }

  // ── refs ──────────────────────────────────────────────────────────────────
  const bubble   = document.getElementById('brain-bubble');
  const panel    = document.getElementById('brain-panel');
  const overlay  = document.getElementById('brain-overlay');
  const fab      = document.getElementById('brain-fab');
  const msgs     = document.getElementById('brain-msgs');
  const input    = document.getElementById('brain-input');
  const sendBtn  = document.getElementById('brain-send');
  const sessView = document.getElementById('brain-sessions-view');
  const sessList = document.getElementById('brain-sessions-list');
  const panelResizeGrip = document.getElementById('brain-resize-grip');
  const inlineResizeGrip = document.getElementById('agent-resize-handle');

  let pendingSelection = '';
  let isStreaming = false;
  let history = [];
  let resizingPanel = false;

  // ── 多会话持久化 ──────────────────────────────────────────────────────────
  const LS_SESSIONS = 'brain-sessions-v2';
  const LS_ACTIVE   = 'brain-active-session-v2';
  let sessions = [];
  let activeId  = null;

  function genId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }

  function relativeTime(ts) {
    const d = Date.now() - ts;
    const m = Math.floor(d / 60000);
    if (m < 1)  return '刚刚';
    if (m < 60) return `${m}分钟前`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}小时前`;
    return `${Math.floor(h / 24)}天前`;
  }

  function loadAllSessions() {
    try {
      const raw = localStorage.getItem(LS_SESSIONS);
      sessions = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(sessions)) sessions = [];
    } catch(e) { sessions = []; }

    // migrate old single-session format
    if (!sessions.length) {
      try {
        const old = localStorage.getItem('brain-chat-v1');
        if (old) {
          const hist = JSON.parse(old);
          if (Array.isArray(hist) && hist.length) {
            const title = hist.find(h => h.role === 'user');
            sessions.push({
              id: genId(),
              title: title ? (title.text || title.content || '').slice(0, 35) : '历史对话',
              history: hist,
              createdAt: Date.now() - 86400000,
              updatedAt: Date.now() - 86400000,
            });
          }
        }
      } catch(e) {}
    }

    activeId = localStorage.getItem(LS_ACTIVE);
    if (inlineMount) {
      activeId = null;
      history = [];
      return;
    }
    if (!activeId || !sessions.find(s => s.id === activeId)) {
      if (sessions.length) {
        activeId = sessions[0].id;
      } else {
        _createSession();
      }
    }
  }

  function saveAllSessions() {
    try {
      localStorage.setItem(LS_SESSIONS, JSON.stringify(sessions));
      localStorage.setItem(LS_ACTIVE, activeId);
    } catch(e) {}
  }

  function _createSession() {
    const s = { id: genId(), title: '', history: [], createdAt: Date.now(), updatedAt: Date.now() };
    sessions.unshift(s);
    activeId = s.id;
    saveAllSessions();
    return s;
  }

  function getActiveSession() {
    return sessions.find(s => s.id === activeId) || null;
  }

  function ensureActiveSession() {
    let s = getActiveSession();
    if (s) return s;
    s = _createSession();
    return s;
  }

  function persistActiveHistory() {
    if (!history.length && !activeId) return;
    ensureActiveSession();
    const s = getActiveSession();
    if (!s) return;
    s.history = history.slice();
    s.updatedAt = Date.now();
    if (!s.title && history.length) {
      const u = history.find(h => h.role === 'user');
      if (u) s.title = (u.text || u.content || '').slice(0, 35);
    }
    saveAllSessions();
  }

  function activateSession(id) {
    activeId = id;
    const s = sessions.find(s => s.id === id);
    history = s ? s.history.slice() : [];
    renderHistoryToDom();
    localStorage.setItem(LS_ACTIVE, activeId);
  }

  function newSession() {
    persistActiveHistory();
    _createSession();
    history = [];
    renderHistoryToDom();
    showChatView();
  }

  function deleteSession(id) {
    const idx = sessions.findIndex(s => s.id === id);
    if (idx === -1) return;
    sessions.splice(idx, 1);
    if (activeId === id) {
      if (sessions.length) {
        activateSession(sessions[0].id);
      } else {
        _createSession();
        history = [];
        msgs.innerHTML = '';
      }
    }
    saveAllSessions();
    renderSessionsList();
  }

  // ── 会话列表渲染 ──────────────────────────────────────────────────────────
  function renderSessionsList() {
    sessList.innerHTML = '';
    if (!sessions.length) {
      sessList.innerHTML = '<div class="bsess-empty">还没有对话记录</div>';
      return;
    }
    for (const s of sessions) {
      const item = document.createElement('div');
      item.className = 'bsess-item' + (s.id === activeId ? ' active' : '');
      item.innerHTML = `
        <div class="bsess-body">
          <div class="bsess-title">${s.title || '新对话'}</div>
          <div class="bsess-meta">${relativeTime(s.updatedAt)}</div>
        </div>
        <button class="bsess-del" title="删除">×</button>
      `;
      item.addEventListener('click', e => {
        if (e.target.classList.contains('bsess-del')) return;
        activateSession(s.id);
        showChatView();
      });
      item.querySelector('.bsess-del').addEventListener('click', e => {
        e.stopPropagation();
        deleteSession(s.id);
      });
      sessList.appendChild(item);
    }
  }

  // ── 视图切换 ──────────────────────────────────────────────────────────────
  function showChatView() {
    sessView.classList.remove('visible');
    msgs.style.display = '';
    document.getElementById('brain-footer').style.display = '';
    document.getElementById('brain-sessions-btn').classList.remove('active');
  }

  function showSessionsView() {
    persistActiveHistory();
    renderSessionsList();
    sessView.classList.add('visible');
    msgs.style.display = 'none';
    document.getElementById('brain-footer').style.display = 'none';
    document.getElementById('brain-sessions-btn').classList.add('active');
  }

  function toggleSessionsView() {
    if (sessView.classList.contains('visible')) showChatView();
    else showSessionsView();
  }

  // ── 消息重渲染 ────────────────────────────────────────────────────────────
  function renderHistoryToDom() {
    msgs.innerHTML = '';
    if (!history.length) {
      const empty = document.createElement('div');
      empty.className = 'brain-empty';
      empty.textContent = '选中文章片段后点“问大脑”，或直接在下方输入，让大脑检索、综合并写回洞察。';
      msgs.appendChild(empty);
      return;
    }
    for (const item of history) {
      if (item.role === 'user') {
        const d = document.createElement('div');
        d.className = 'bmsg-user';
        if (item.quote) {
          const q = document.createElement('div');
          q.className = 'bmsg-quote';
          q.textContent = item.quote.length > 120 ? item.quote.slice(0, 120) + '…' : item.quote;
          d.appendChild(q);
        }
        const t = document.createElement('div');
        t.textContent = item.text || item.content || '';
        d.appendChild(t);
        msgs.appendChild(d);
      } else if (item.role === 'assistant') {
        const d = document.createElement('div');
        d.className = 'bmsg-assistant';
        d.innerHTML = md(item.content || '');
        msgs.appendChild(d);
      }
    }
    msgs.scrollTop = msgs.scrollHeight;
  }

  // ── 面板开关 ───────────────────────────────────────────────────────────────
  function openPanel() {
    if (inlineMount) {
      inlineMount.classList.remove('hidden');
      if (inlineResizeGrip) inlineResizeGrip.classList.remove('hidden');
    }
    panel.classList.add('open');
    if (!inlineMount) overlay.classList.add('open');
    setTimeout(() => input.focus(), inlineMount ? 0 : 280);
  }
  function closePanel() {
    if (inlineMount) {
      panel.classList.remove('open');
      inlineMount.classList.add('hidden');
      if (inlineResizeGrip) inlineResizeGrip.classList.add('hidden');
      input.blur();
      return;
    }
    panel.classList.remove('open');
    overlay.classList.remove('open');
    showChatView();
  }

  document.getElementById('brain-close').addEventListener('click', closePanel);
  overlay.addEventListener('click', closePanel);
  fab.addEventListener('click', () => { pendingSelection = ''; openPanel(); });
  document.getElementById('brain-sessions-btn').addEventListener('click', toggleSessionsView);
  document.getElementById('brain-new-btn').addEventListener('click', newSession);
  document.getElementById('brain-new-chat-btn').addEventListener('click', newSession);

  if (panelResizeGrip && !inlineMount) {
    panelResizeGrip.addEventListener('mousedown', e => {
      resizingPanel = true;
      panelResizeGrip.classList.add('dragging');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', e => {
      if (!resizingPanel) return;
      const width = Math.min(Math.max(window.innerWidth - e.clientX, 300), Math.min(760, window.innerWidth * 0.78));
      panel.style.width = `${width}px`;
      panel.style.maxWidth = 'none';
    });

    document.addEventListener('mouseup', () => {
      if (!resizingPanel) return;
      resizingPanel = false;
      panelResizeGrip.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  }

  // ── 初始化会话 ────────────────────────────────────────────────────────────
  loadAllSessions();
  if (activeId) activateSession(activeId);
  else renderHistoryToDom();

  // ── 选中气泡 ──────────────────────────────────────────────────────────────
  document.addEventListener('mouseup', e => {
    if (panel.contains(e.target) || bubble.contains(e.target)) return;
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : '';
      if (text.length < 8) { bubble.style.display = 'none'; return; }
      pendingSelection = text;
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      bubble.style.display = 'flex';
      bubble.style.top  = `${rect.top  + window.scrollY - 42}px`;
      bubble.style.left = `${rect.left + window.scrollX + rect.width / 2 - 42}px`;
    }, 10);
  });

  document.addEventListener('mousedown', e => {
    if (!bubble.contains(e.target)) bubble.style.display = 'none';
  });

  bubble.addEventListener('click', () => {
    bubble.style.display = 'none';
    openPanel();
    input.focus();
  });

  // ── Markdown 渲染 ─────────────────────────────────────────────────────────
  function md(text) {
    return text
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
      .replace(/\*(.+?)\*/g,'<em>$1</em>')
      .replace(/`([^`\n]+)`/g,'<code>$1</code>')
      .replace(/^#{1,3}\s+(.+)$/gm,'<h3>$1</h3>')
      .replace(/^>\s+(.+)$/gm,'<blockquote>$1</blockquote>')
      .replace(/^---$/gm,'<hr>')
      .replace(/^[-•]\s+(.+)$/gm,'<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)/g, m => `<ul>${m}</ul>`)
      .split(/\n\n+/).map(p => {
        if (/^<[hublH]/.test(p.trim())) return p.trim();
        return `<p>${p.trim()}</p>`;
      }).join('');
  }

  // ── DOM 构建助手 ──────────────────────────────────────────────────────────
  const TOOL_ICONS = {
    recall: '🔍', synthesize: '🧠', write_insight: '✏️',
    list_recent_articles: '📚', get_brain_stats: '📊',
  };

  function addUserMsg(text, quote) {
    const empty = msgs.querySelector('.brain-empty');
    if (empty) empty.remove();
    const d = document.createElement('div');
    d.className = 'bmsg-user';
    if (quote) {
      const q = document.createElement('div');
      q.className = 'bmsg-quote';
      q.textContent = quote.length > 120 ? quote.slice(0,120)+'…' : quote;
      d.appendChild(q);
    }
    const s = document.createElement('span');
    s.textContent = text;
    d.appendChild(s);
    msgs.appendChild(d);
    scroll();
    return d;
  }

  function addThinking(text) {
    const d = document.createElement('div');
    d.className = 'brain-thinking';
    d.innerHTML = `
      <div class="brain-thinking-dots"><span></span><span></span><span></span></div>
      <span class="brain-thinking-text">${text}</span>`;
    msgs.appendChild(d);
    scroll();
    return d;
  }

  function updateThinking(el, text) {
    const t = el.querySelector('.brain-thinking-text');
    if (t) t.textContent = text;
  }

  function addToolBlock(name, args) {
    const icon = TOOL_ICONS[name] || '⚙️';
    const argStr = Object.values(args).join(' ').slice(0, 40);
    const d = document.createElement('div');
    d.className = 'brain-tool';
    d.innerHTML = `
      <div class="brain-tool-header">
        <span class="brain-tool-icon">${icon}</span>
        <span class="brain-tool-name">${name}</span>
        <span class="brain-tool-args">${argStr}</span>
        <span class="brain-tool-chevron">▾</span>
      </div>
      <div class="brain-tool-body"></div>`;
    d.querySelector('.brain-tool-header').addEventListener('click', () => d.classList.toggle('open'));
    msgs.appendChild(d);
    scroll();
    return d;
  }

  function fillToolResult(toolEl, result) {
    toolEl.querySelector('.brain-tool-body').textContent = result;
  }

  function addAssistantMsg() {
    const d = document.createElement('div');
    d.className = 'bmsg-assistant';
    msgs.appendChild(d);
    return d;
  }

  function scroll() { msgs.scrollTop = msgs.scrollHeight; }

  // ── 发送 ──────────────────────────────────────────────────────────────────
  async function send() {
    if (isStreaming) return;
    const text = input.value.trim();
    const quote    = pendingSelection || '';
    const userText = text || '分析一下这段内容。';
    const fullMsg  = quote
      ? `以下是我选中的内容：\n「${quote}」\n\n${userText}`
      : userText;

    // 切换到 chat 视图（如果正在看会话列表）
    if (sessView.classList.contains('visible')) showChatView();
    ensureActiveSession();

    addUserMsg(userText, quote);
    pendingSelection = '';
    input.value = '';
    autoResize();

    isStreaming = true;
    sendBtn.disabled = true;

    let thinkingEl = addThinking('正在思考…');
    let currentToolEl = null;
    let assistantEl = null;
    let accumulated = '';

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: fullMsg, history }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const lines = buf.split('\n');
        buf = lines.pop();

        for (const line of lines) {
          const raw = line.trim();
          if (!raw) continue;
          let ev;
          try { ev = JSON.parse(raw); } catch { continue; }

          switch (ev.type) {
            case 'thinking':
              if (thinkingEl) updateThinking(thinkingEl, ev.text);
              else thinkingEl = addThinking(ev.text);
              break;

            case 'tool_start':
              if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
              currentToolEl = addToolBlock(ev.name, ev.args || {});
              break;

            case 'tool_end':
              if (currentToolEl) {
                fillToolResult(currentToolEl, ev.result || '');
                currentToolEl = null;
              }
              thinkingEl = addThinking('继续思考…');
              break;

            case 'text':
              if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
              if (!assistantEl) assistantEl = addAssistantMsg();
              accumulated += ev.chunk;
              assistantEl.innerHTML = md(accumulated);
              scroll();
              break;

            case 'done':
              if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
              break;
          }
        }
      }

      history.push({ role: 'user', content: fullMsg, text: userText, quote });
      history.push({ role: 'assistant', content: accumulated });
      if (history.length > 20) history = history.slice(-20);
      persistActiveHistory();

    } catch (err) {
      if (thinkingEl) thinkingEl.remove();
      const d = addAssistantMsg();
      d.textContent = '出错了：' + err.message;
    } finally {
      isStreaming = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }
  input.addEventListener('input', autoResize);
})();
