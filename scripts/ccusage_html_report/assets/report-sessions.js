function renderSessionFilter() {
  const el = document.getElementById('sessionFilter');
  const pills = [];
  if (state.selected) {
    pills.push(`Filtered by ${esc(state.period)}: ${esc(state.selected.label)} / ${esc(seriesLabel(state.selected.series))}`);
  }
  if (state.query) pills.push(`Search: ${esc(state.query)}`);
  if (state.filters.agent) pills.push(`Agent: ${esc(state.filters.agent)}`);
  if (state.filters.model) pills.push(`Model: ${esc(state.filters.model)}`);
  if (state.filters.transcript === 'with') pills.push('With transcript');
  if (state.filters.transcript === 'without') pills.push('No transcript');
  if (state.filters.dateFrom) pills.push(`From: ${esc(state.filters.dateFrom)}`);
  if (state.filters.dateTo) pills.push(`To: ${esc(state.filters.dateTo)}`);
  if (!pills.length) {
    el.innerHTML = '';
    return;
  }
  el.innerHTML = pills.map(pill => `<span class="pill">${pill}</span>`).join('') + '<button id="clearSessionFilter">Clear filters</button>';
  document.getElementById('clearSessionFilter').onclick = clearSessionFilters;
}
function bucketMatchesSession(s) {
  if (!state.selected) return true;
  const key = state.period === 'daily' ? 'date' : state.period === 'weekly' ? 'week' : 'month';
  if (String(s[key] || '') !== state.selected.label) return false;
  if (state.selected.series !== '__total' && !(s.modelNames || []).includes(state.selected.series)) return false;
  return true;
}
function filteredSessions() {
  const q = state.query.toLowerCase();
  let sessions = (DATA.sessions || []).filter(bucketMatchesSession).filter(sessionMatchesManualFilters);
  if (q) {
    sessions = sessions.filter(s => {
      const hay = [
        s.title,
        s.agentName,
        s.sessionId,
        s.sessionFile,
        s.transcriptPath,
        s.date,
        s.week,
        s.month,
        s.lastActivityAt,
        ...(s.modelNames || []),
        ...((s.snippets || []).map(x => x.text)),
        ...((s.conversation || []).map(x => x.text))
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }
  sessions.sort((a, b) => {
    if (state.sort === 'tokens') return Number(b.totalTokens || 0) - Number(a.totalTokens || 0);
    if (state.sort === 'cost') return Number(b.costUSD || 0) - Number(a.costUSD || 0);
    if (state.sort === 'title') return String(a.title || '').localeCompare(String(b.title || ''));
    if (state.sort === 'oldest') return (sessionTime(a) - sessionTime(b)) || compareTitle(a, b);
    return (sessionTime(b) - sessionTime(a)) || compareTitle(a, b);
  });
  return sessions;
}
function sessionKey(s) {
  return String(s.reportSessionId || s.sessionId || s.sessionFile || s.title || '');
}
function drawerWidthBounds() {
  const shell = document.querySelector('.sessions-shell');
  const rect = shell ? shell.getBoundingClientRect() : null;
  const shellWidth = rect && rect.width > 0 ? rect.width : Math.max(960, window.innerWidth - 80);
  const min = 360;
  const max = Math.max(min, Math.min(1120, Math.round(shellWidth - 320)));
  return {min, max};
}
function clampDrawerWidth(width) {
  const bounds = drawerWidthBounds();
  const numeric = Number(width);
  if (!Number.isFinite(numeric)) return 440;
  return Math.min(Math.max(Math.round(numeric), bounds.min), bounds.max);
}
function saveDrawerWidth() {
  try {
    window.localStorage.setItem('ccusage.sessionDrawerWidth', String(state.drawerWidth));
  } catch (_) {}
}
function applySessionDrawerWidth() {
  const shell = document.querySelector('.sessions-shell');
  const resizer = document.getElementById('sessionDrawerResizer');
  if (!shell) return;
  state.drawerWidth = clampDrawerWidth(state.drawerWidth);
  shell.style.setProperty('--session-drawer-width', `${state.drawerWidth}px`);
  if (resizer) {
    const bounds = drawerWidthBounds();
    resizer.setAttribute('aria-valuemin', String(bounds.min));
    resizer.setAttribute('aria-valuemax', String(bounds.max));
    resizer.setAttribute('aria-valuenow', String(state.drawerWidth));
  }
}
function setupSessionDrawerResize() {
  const resizer = document.getElementById('sessionDrawerResizer');
  if (!resizer) return;
  let drag = null;
  applySessionDrawerWidth();
  resizer.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    event.preventDefault();
    drag = {startX: event.clientX, startWidth: state.drawerWidth};
    resizer.setPointerCapture(event.pointerId);
    document.body.classList.add('resizing-session-drawer');
  });
  resizer.addEventListener('pointermove', event => {
    if (!drag) return;
    state.drawerWidth = clampDrawerWidth(drag.startWidth - (event.clientX - drag.startX));
    applySessionDrawerWidth();
  });
  const finishDrag = event => {
    if (!drag) return;
    drag = null;
    document.body.classList.remove('resizing-session-drawer');
    if (event && resizer.hasPointerCapture(event.pointerId)) resizer.releasePointerCapture(event.pointerId);
    saveDrawerWidth();
  };
  resizer.addEventListener('pointerup', finishDrag);
  resizer.addEventListener('pointercancel', finishDrag);
  resizer.addEventListener('keydown', event => {
    const bounds = drawerWidthBounds();
    const step = event.shiftKey ? 80 : 24;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      state.drawerWidth = clampDrawerWidth(state.drawerWidth + (event.key === 'ArrowLeft' ? step : -step));
      applySessionDrawerWidth();
      saveDrawerWidth();
    } else if (event.key === 'Home') {
      event.preventDefault();
      state.drawerWidth = bounds.min;
      applySessionDrawerWidth();
      saveDrawerWidth();
    } else if (event.key === 'End') {
      event.preventDefault();
      state.drawerWidth = bounds.max;
      applySessionDrawerWidth();
      saveDrawerWidth();
    }
  });
  window.addEventListener('resize', () => {
    applySessionDrawerWidth();
    saveDrawerWidth();
  });
}
function metricBlock(label, value) {
  return `<div class="metric-mini"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
}
function modelPrice(model) {
  return (((DATA.modelPrices || {}).models || {})[model]) || null;
}
function priceBlocks(price) {
  const hasAnyRate = price && ['input', 'output', 'cacheRead', 'cacheCreation'].some((key) => price[key] !== undefined && price[key] !== null && !Number.isNaN(Number(price[key])));
  if (!price || price.source === 'unavailable' || price.source === 'disabled' || !hasAnyRate) {
    return '<div class="price-strip muted">Current price unavailable.</div>';
  }
  const blocks = [
    ['Input', priceMoney(price.input)],
    ['Output', priceMoney(price.output)],
    ['Cache hit', priceMoney(price.cacheRead)]
  ];
  if (price.cacheCreation !== undefined && price.cacheCreation !== null) blocks.push(['Cache write', priceMoney(price.cacheCreation)]);
  return `<div class="price-strip">
    <div class="meta">Current price · ${esc(price.unit || 'USD per 1M tokens')} · ${esc(price.source || '')}</div>
    <div class="model-metrics">${blocks.map(([label, value]) => metricBlock(label, value)).join('')}</div>
  </div>`;
}
function modelRows(models) {
  const entries = Object.entries(models || {});
  if (!entries.length) return '<div class="muted">No per-model breakdown available.</div>';
  return `<div class="model-breakdown">${entries.map(([name, m]) => `<div class="model-breakdown-row">
    <div class="name">${esc(name)}</div>
    <div class="model-metrics">
      ${[
        ['Total', fmt(m.totalTokens)],
        ['Input', fmt(m.inputTokens)],
        ['Output', fmt(m.outputTokens)],
        ['Reasoning', fmt(m.reasoningOutputTokens)],
        ['Cache', fmt(Number(m.cacheCreationTokens || 0) + Number(m.cacheReadTokens || 0))],
        ['Context', fmt(m.contextTokens)],
        ['Cost', money(m.costUSD)]
      ].map(([label, value]) => metricBlock(label, value)).join('')}
    </div>
  </div>`).join('')}</div>`;
}
function conversationLimit(s) {
  const key = sessionKey(s);
  return Number(state.conversationLimits.get(key) || state.conversationBatch);
}
function messageContentHtml(text) {
  if (state.messageRenderMode === 'markdown') {
    return `<div class="markdown-body">${markdownToHtml(text)}</div>`;
  }
  return `<div class="text raw-text">${esc(text)}</div>`;
}
function messageRenderSwitchHtml() {
  return `<div class="message-render-switch" role="group" aria-label="Conversation display mode">
    <button class="render-mode-btn ${state.messageRenderMode === 'raw' ? 'active' : ''}" data-message-render-mode="raw" aria-pressed="${state.messageRenderMode === 'raw'}">Raw</button>
    <button class="render-mode-btn ${state.messageRenderMode === 'markdown' ? 'active' : ''}" data-message-render-mode="markdown" aria-pressed="${state.messageRenderMode === 'markdown'}">Rendered</button>
  </div>`;
}
function turnHtml(turn) {
  const role = turn.role === 'assistant' ? 'assistant' : 'user';
  const roleLabel = role === 'assistant' ? 'Agent' : 'You';
  const avatar = role === 'assistant' ? 'AI' : 'You';
  return `<div class="turn ${role}">
    <div class="chat-avatar">${avatar}</div>
    <div class="chat-bubble">
      <div class="chat-meta"><b>${roleLabel}</b><span>${esc(turn.time || '')}</span><span>${fmt(turn.chars)} chars</span></div>
      ${messageContentHtml(turn.text)}
    </div>
  </div>`;
}
function conversationHtml(s) {
  const turns = s.conversation || [];
  if (!turns.length) {
    return '<div class="muted">No full transcript available for this session. Codex sessions include full local conversation when the JSONL file can be located.</div>';
  }
  const key = sessionKey(s);
  const visibleTurns = turns.slice(0, conversationLimit(s));
  const remaining = Math.max(0, turns.length - visibleTurns.length);
  return `<div class="conversation-head">
    <div class="conversation-status">
      <span class="conversation-count" data-total="${turns.length}">Showing ${fmt(visibleTurns.length)} of ${fmt(turns.length)} turns</span>
      <span class="conversation-remaining">${remaining ? fmt(remaining) + ' more' : 'Complete'}</span>
    </div>
    ${messageRenderSwitchHtml()}
  </div>
  <div class="conversation" data-session-key="${esc(key)}" data-visible="${visibleTurns.length}" data-total="${turns.length}">${visibleTurns.map(turnHtml).join('')}</div>
  ${remaining ? `<div class="load-row conversation-load-row"><button class="conversation-load" data-session-key="${esc(key)}">Load more turns</button></div>` : ''}`;
}
function sessionDetailHtml(s) {
  const detailMetrics = [
    ['Total', fmt(s.totalTokens)],
    ['Input', fmt(s.inputTokens)],
    ['Output', fmt(s.outputTokens)],
    ['Reasoning', fmt(s.reasoningOutputTokens)],
    ['Cache create', fmt(s.cacheCreationTokens)],
    ['Cache read', fmt(s.cacheReadTokens)],
    ['Context', fmt(s.contextTokens)],
    ['Generation', fmt(s.generationTokens)],
    ['Cost', money(s.costUSD)]
  ].map(([label, value]) => metricBlock(label, value)).join('');
  const models = (s.modelNames || []).join(', ') || 'model n/a';
  return `<div class="drawer-head">
    <div class="drawer-title">
      <h3>${esc(s.title || s.sessionId || 'Untitled session')}</h3>
      <div class="meta">
        <span>${esc(s.date || '')}</span>
        <span>${esc(s.agentName || DATA.agent || '')}</span>
        <span>${esc(models)}</span>
      </div>
    </div>
    <button class="drawer-close" aria-label="Close session details">Close</button>
  </div>
  <div class="drawer-scroll">
    <div class="session-detail">
      <section class="detail-section">
        <h3>Usage</h3>
        <div class="detail-grid">${detailMetrics}</div>
      </section>
      <section class="detail-section">
        <h3>Models</h3>
        ${modelRows(s.models)}
      </section>
      <section class="detail-section">
        <h3>Conversation</h3>
        ${conversationHtml(s)}
      </section>
      ${s.transcriptPath ? `<section class="detail-section"><h3>Transcript</h3><div class="meta session-id">${esc(s.transcriptPath)}</div></section>` : ''}
    </div>
  </div>`;
}
function sessionHtml(s) {
  const snippets = (s.snippets || []).slice(0, 4).map(sn => `<div class="snippet ${sn.role === 'assistant' ? 'assistant' : ''}"><b>${esc(sn.role)}:</b> ${esc(sn.text)}</div>`).join('');
  const models = (s.modelNames || []).join(', ') || 'model n/a';
  const key = sessionKey(s);
  const isActive = state.activeSessionKey === key;
  const metrics = [
    ['Total', fmt(s.totalTokens)],
    ['Input', fmt(s.inputTokens)],
    ['Output', fmt(s.outputTokens)],
    ['Reasoning', fmt(s.reasoningOutputTokens)],
    ['Context', fmt(s.contextTokens)],
    ['Cost', money(s.costUSD)]
  ].map(([label, value]) => `<div class="metric-mini"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
  return `<article class="session-card ${isActive ? 'active' : ''}" data-session-key="${esc(key)}">
    <div class="session-top">
      <div>
        <h3>${esc(s.title || s.sessionId || 'Untitled session')}</h3>
        <div class="meta">
          <span>${esc(s.date || '')}</span>
          <span>${esc(s.agentName || DATA.agent || '')}</span>
          <span>${esc(models)}</span>
        </div>
      </div>
      <div class="meta session-id">${esc(s.sessionId || s.sessionFile || '')}</div>
    </div>
    <div class="session-metrics">${metrics}</div>
    <div class="snippets">${snippets || '<span class="muted">No transcript snippets embedded.</span>'}</div>
    <button class="detail-toggle" data-session-key="${esc(key)}">${isActive ? 'Close details' : 'View details'}</button>
  </article>`;
}
function renderSessionDrawer(activeSession) {
  const drawer = document.getElementById('sessionDrawer');
  if (!activeSession) {
    drawer.classList.add('empty');
    drawer.innerHTML = `<div class="drawer-empty">
      <h3>Select a session</h3>
      <div>Details, model breakdowns, and the full conversation will stay here while the session list remains stable.</div>
    </div>`;
    return;
  }
  drawer.classList.remove('empty');
  drawer.innerHTML = sessionDetailHtml(activeSession);
  const close = drawer.querySelector('.drawer-close');
  if (close) close.onclick = () => {
    state.activeSessionKey = null;
    renderSessions();
  };
  bindConversationLoad(activeSession);
  bindMessageRenderSwitch();
}
function bindSessionCards(root) {
  root.querySelectorAll('.session-card').forEach(card => card.onclick = event => {
    if (event.target.closest('button')) return;
    const key = card.dataset.sessionKey;
    if (state.activeSessionKey !== key) {
      state.activeSessionKey = key;
      renderSessions();
    }
  });
  root.querySelectorAll('.detail-toggle').forEach(btn => btn.onclick = () => {
    const key = btn.dataset.sessionKey;
    state.activeSessionKey = state.activeSessionKey === key ? null : key;
    renderSessions();
  });
}
function updateSessionCount(sessions, visibleCount) {
  const count = document.getElementById('sessionCount');
  count.textContent = `Showing ${visibleCount} of ${sessions.length} matching session${sessions.length === 1 ? '' : 's'}`;
  document.getElementById('loadMore').style.display = sessions.length > visibleCount ? 'inline-flex' : 'none';
}
function appendSessionCards() {
  const sessions = filteredSessions();
  const container = document.getElementById('sessions');
  const previousLimit = Math.min(state.limit, sessions.length);
  const nextLimit = Math.min(sessions.length, previousLimit + 80);
  if (nextLimit <= previousLimit) return;
  state.limit = nextLimit;
  container.insertAdjacentHTML('beforeend', sessions.slice(previousLimit, nextLimit).map(sessionHtml).join(''));
  bindSessionCards(container);
  updateSessionCount(sessions, nextLimit);
}
function bindConversationLoad(activeSession) {
  const drawer = document.getElementById('sessionDrawer');
  const loadConversation = drawer.querySelector('.conversation-load');
  if (!loadConversation) return;
  loadConversation.onclick = () => appendConversationTurns(activeSession);
}
function bindMessageRenderSwitch() {
  document.querySelectorAll('.render-mode-btn').forEach(btn => btn.onclick = () => {
    const mode = btn.dataset.messageRenderMode === 'markdown' ? 'markdown' : 'raw';
    if (state.messageRenderMode === mode) return;
    state.messageRenderMode = mode;
    try {
      window.localStorage.setItem('ccusage.messageRenderMode', mode);
    } catch (_) {}
    renderSessions();
  });
}
function appendConversationTurns(activeSession) {
  const key = sessionKey(activeSession);
  const turns = activeSession.conversation || [];
  const drawer = document.getElementById('sessionDrawer');
  const conversation = drawer.querySelector('.conversation');
  const loadButton = drawer.querySelector('.conversation-load');
  if (!conversation || !loadButton) return;

  const current = Number(conversation.dataset.visible || 0);
  const nextLimit = Math.min(turns.length, current + state.conversationBatch);
  const nextTurns = turns.slice(current, nextLimit);
  if (!nextTurns.length) return;

  loadButton.disabled = true;
  conversation.insertAdjacentHTML('beforeend', nextTurns.map(turnHtml).join(''));
  conversation.dataset.visible = String(nextLimit);
  state.conversationLimits.set(key, nextLimit);

  const remaining = Math.max(0, turns.length - nextLimit);
  const count = drawer.querySelector('.conversation-count');
  const remainingEl = drawer.querySelector('.conversation-remaining');
  if (count) count.textContent = `Showing ${fmt(nextLimit)} of ${fmt(turns.length)} turns`;
  if (remainingEl) remainingEl.textContent = remaining ? `${fmt(remaining)} more` : 'Complete';

  if (remaining) {
    loadButton.disabled = false;
    loadButton.textContent = 'Load more turns';
  } else {
    const loadRow = loadButton.closest('.conversation-load-row');
    if (loadRow) loadRow.remove();
  }
}
function renderSessions() {
  applySessionDrawerWidth();
  const sessions = filteredSessions();
  let activeSession = state.activeSessionKey ? sessions.find(s => sessionKey(s) === state.activeSessionKey) : null;
  if (state.activeSessionKey && !activeSession) {
    state.activeSessionKey = null;
    activeSession = null;
  }
  const container = document.getElementById('sessions');
  container.className = 'sessions ' + state.view;
  document.getElementById('cardsBtn').classList.toggle('active', state.view === 'cards');
  document.getElementById('listBtn').classList.toggle('active', state.view === 'list');
  const visibleSessions = sessions.slice(0, state.limit);
  updateSessionCount(sessions, visibleSessions.length);
  container.innerHTML = visibleSessions.length ? visibleSessions.map(sessionHtml).join('') : '<div class="empty-state">No sessions match the current filters.</div>';
  bindSessionCards(container);
  renderSessionDrawer(activeSession);
}
