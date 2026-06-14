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
        ...((s.conversation || []).flatMap(x => [x.text, x.toolName, x.toolResult]))
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
function setMessageRenderButtons() {
  document.querySelectorAll('.render-mode-btn').forEach(btn => {
    const active = btn.dataset.messageRenderMode === state.messageRenderMode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });
}
function messageRenderSwitchHtml() {
  return `<div class="message-render-switch" role="group" aria-label="Conversation display mode">
    <button class="render-mode-btn ${state.messageRenderMode === 'raw' ? 'active' : ''}" data-message-render-mode="raw" aria-pressed="${state.messageRenderMode === 'raw'}">Raw</button>
    <button class="render-mode-btn ${state.messageRenderMode === 'markdown' ? 'active' : ''}" data-message-render-mode="markdown" aria-pressed="${state.messageRenderMode === 'markdown'}">Rendered</button>
  </div>`;
}
function normalizedTurnRole(turn) {
  const role = String(turn.role || '').toLowerCase();
  if (role === 'assistant' || role === 'tool') return role;
  return 'user';
}
function toolTurnKey(sessionKeyValue, index) {
  return `${sessionKeyValue}::${index}`;
}
function toolTextParts(turn) {
  const text = String(turn.text || '').trim();
  const explicitResult = String(turn.toolResult || '').trim();
  if (explicitResult) return {summary: text || 'Tool call', result: explicitResult};

  const match = text.match(/(?:^|\n)(?:Output|Result|Response):\s*/i);
  if (match && text.slice(0, match.index).trim().startsWith('Tool call:')) {
    const summary = text.slice(0, match.index).trim();
    const result = text.slice(match.index + match[0].length).trim();
    if (result) return {summary: summary || 'Tool call', result};
  }
  return {summary: text || 'Tool call', result: ''};
}
function trimToolPreviewLine(line, maxChars = 260) {
  const text = String(line || '').trimEnd();
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars - 3).trimEnd() + '...';
}
function toolPreviewText(summary) {
  const lines = String(summary || '').replace(/\r\n?/g, '\n').split('\n');
  const prefixes = ['Tool call:', 'Command:', 'Workdir:', 'Description:', 'Status:'];
  const preview = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (!preview.length || prefixes.some(prefix => trimmed.startsWith(prefix))) {
      preview.push(trimToolPreviewLine(trimmed));
    }
    if (preview.length >= 4) break;
  }
  if (preview.length) return preview.join('\n');
  return lines.slice(0, 3).map(line => trimToolPreviewLine(line)).join('\n').trim();
}
function toolSectionButtonHtml(turnKey, section, expanded) {
  const isResult = section === 'result';
  const text = isResult ? (expanded ? 'Hide result' : 'Show result') : (expanded ? 'Hide call' : 'Show call');
  return `<button class="tool-section-toggle" type="button" data-tool-turn-key="${esc(turnKey)}" data-tool-section="${section}" aria-pressed="${expanded}">${text}</button>`;
}
function conversationHeaderControlsHtml(s) {
  const turns = s.conversation || [];
  if (!turns.length) return '';
  const visible = Math.min(turns.length, conversationLimit(s));
  const remaining = Math.max(0, turns.length - visible);
  return `<div class="drawer-conversation-controls">
    <div class="conversation-status">
      <span class="conversation-count" data-total="${turns.length}">Showing ${fmt(visible)} of ${fmt(turns.length)} turns</span>
      <span class="conversation-remaining">${remaining ? fmt(remaining) + ' more' : 'Complete'}</span>
    </div>
    ${messageRenderSwitchHtml()}
  </div>`;
}
function toolTurnHtml(turn, index, sessionKeyValue) {
  const turnKey = toolTurnKey(sessionKeyValue, index);
  const parts = toolTextParts(turn);
  const preview = toolPreviewText(parts.summary);
  const hasCallDetails = preview && preview.trim() !== parts.summary.trim();
  const hasResult = Boolean(parts.result);
  const callExpanded = hasCallDetails ? state.expandedToolCalls.has(turnKey) : true;
  const resultExpanded = hasResult && state.expandedToolResults.has(turnKey);
  const defaultSection = hasResult ? 'result' : hasCallDetails ? 'call' : '';
  const expandableAttrs = defaultSection
    ? ` data-tool-turn-key="${esc(turnKey)}" data-default-tool-section="${defaultSection}" tabindex="0" aria-expanded="${defaultSection === 'result' ? resultExpanded : callExpanded}" title="${defaultSection === 'result' ? 'Toggle tool result' : 'Toggle tool call'}"`
    : '';
  const callButtons = hasCallDetails ? toolSectionButtonHtml(turnKey, 'call', callExpanded) : '';
  const resultButtons = hasResult ? toolSectionButtonHtml(turnKey, 'result', resultExpanded) : '';
  const resultChars = Number(turn.toolResultChars || parts.result.length || 0);
  const toolName = turn.toolName ? `<span>${esc(turn.toolName)}</span>` : '';
  return `<div class="turn tool ${defaultSection ? 'tool-expandable' : ''} ${callExpanded ? 'tool-call-expanded' : 'tool-call-collapsed'} ${resultExpanded ? 'tool-result-expanded' : 'tool-result-collapsed'}" data-tool-turn-key="${esc(turnKey)}">
    <div class="chat-avatar">Tool</div>
    <div class="chat-bubble"${expandableAttrs}>
      <div class="chat-meta"><b>Tool</b>${toolName}<span>${esc(turn.time || '')}</span><span>${fmt(turn.chars)} chars</span>${hasResult ? `<span>${fmt(resultChars)} result chars</span>` : ''}${callButtons}${resultButtons}</div>
      <div class="tool-call-preview ${callExpanded ? 'hidden' : ''}">${messageContentHtml(preview || parts.summary)}</div>
      <div class="tool-call-full ${callExpanded ? '' : 'hidden'}">${messageContentHtml(parts.summary)}</div>
      ${hasResult ? `<div class="tool-result ${resultExpanded ? '' : 'hidden'}"><div class="tool-result-label">Result</div>${messageContentHtml(parts.result)}</div>` : ''}
    </div>
  </div>`;
}
function turnHtml(turn, index = 0, sessionKeyValue = '') {
  const role = normalizedTurnRole(turn);
  if (role === 'tool') return toolTurnHtml(turn, index, sessionKeyValue);
  const roleLabel = role === 'assistant' ? 'Agent' : role === 'tool' ? 'Tool' : 'You';
  const avatar = role === 'assistant' ? 'AI' : role === 'tool' ? 'Tool' : 'You';
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
    return '<div class="muted">No full transcript available for this session. Codex and Gemini sessions include local conversation when matching transcript files can be located.</div>';
  }
  const key = sessionKey(s);
  const visibleTurns = turns.slice(0, conversationLimit(s));
  const remaining = Math.max(0, turns.length - visibleTurns.length);
  return `<div class="conversation" data-session-key="${esc(key)}" data-visible="${visibleTurns.length}" data-total="${turns.length}">${visibleTurns.map((turn, index) => turnHtml(turn, index, key)).join('')}</div>
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
      ${conversationHeaderControlsHtml(s)}
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
  const snippets = (s.snippets || []).slice(0, 4).map(sn => {
    const role = normalizedTurnRole(sn);
    return `<div class="snippet ${role === 'assistant' ? 'assistant' : role === 'tool' ? 'tool' : ''}"><b>${esc(role)}:</b> ${esc(sn.text)}</div>`;
  }).join('');
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
  bindMessageRenderSwitch(activeSession);
  bindToolTurnToggles(activeSession);
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
function bindMessageRenderSwitch(activeSession) {
  document.querySelectorAll('.render-mode-btn').forEach(btn => btn.onclick = () => {
    const mode = btn.dataset.messageRenderMode === 'markdown' ? 'markdown' : 'raw';
    if (state.messageRenderMode === mode) return;
    state.messageRenderMode = mode;
    try {
      window.localStorage.setItem('ccusage.messageRenderMode', mode);
    } catch (_) {}
    updateConversationRenderMode(activeSession);
  });
}
function toolTurnElement(turnKey) {
  let found = null;
  document.querySelectorAll('.turn.tool[data-tool-turn-key]').forEach(turn => {
    if (turn.dataset.toolTurnKey === turnKey) found = turn;
  });
  return found;
}
function setToolSectionDom(turn, section, expanded) {
  if (!turn) return;
  if (section === 'call') {
    turn.classList.toggle('tool-call-expanded', expanded);
    turn.classList.toggle('tool-call-collapsed', !expanded);
    const preview = turn.querySelector('.tool-call-preview');
    const full = turn.querySelector('.tool-call-full');
    if (preview) preview.classList.toggle('hidden', expanded);
    if (full) full.classList.toggle('hidden', !expanded);
  } else {
    turn.classList.toggle('tool-result-expanded', expanded);
    turn.classList.toggle('tool-result-collapsed', !expanded);
    const result = turn.querySelector('.tool-result');
    if (result) result.classList.toggle('hidden', !expanded);
  }

  turn.querySelectorAll(`.tool-section-toggle[data-tool-section="${section}"]`).forEach(btn => {
    const isResult = section === 'result';
    btn.textContent = isResult ? (expanded ? 'Hide result' : 'Show result') : (expanded ? 'Hide call' : 'Show call');
    btn.setAttribute('aria-pressed', String(expanded));
  });

  const bubble = turn.querySelector('.chat-bubble[data-default-tool-section]');
  if (bubble && bubble.dataset.defaultToolSection === section) {
    bubble.setAttribute('aria-expanded', String(expanded));
  }
}
function withStableToolScroll(turn, action) {
  const drawer = document.getElementById('sessionDrawer');
  const drawerScroll = drawer ? drawer.querySelector('.drawer-scroll') : null;
  if (!turn || !drawerScroll) {
    action();
    return;
  }
  const before = turn.getBoundingClientRect().top;
  action();
  window.requestAnimationFrame(() => {
    drawerScroll.scrollTop += turn.getBoundingClientRect().top - before;
  });
}
function toggleToolSection(turnKey, section) {
  if (!turnKey || !section) return;
  const expandedSet = section === 'result' ? state.expandedToolResults : state.expandedToolCalls;
  const expanded = !expandedSet.has(turnKey);
  if (expanded) expandedSet.add(turnKey);
  else expandedSet.delete(turnKey);
  const turn = toolTurnElement(turnKey);
  withStableToolScroll(turn, () => setToolSectionDom(turn, section, expanded));
}
function bindToolTurnToggles(activeSession) {
  const drawer = document.getElementById('sessionDrawer');
  if (!drawer || !activeSession) return;
  drawer.querySelectorAll('.tool-section-toggle').forEach(btn => btn.onclick = event => {
    event.stopPropagation();
    toggleToolSection(btn.dataset.toolTurnKey, btn.dataset.toolSection);
  });
  drawer.querySelectorAll('.turn.tool .chat-bubble[data-default-tool-section]').forEach(bubble => {
    bubble.onclick = event => {
      if (event.target.closest('button, a')) return;
      toggleToolSection(bubble.dataset.toolTurnKey, bubble.dataset.defaultToolSection);
    };
    bubble.onkeydown = event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      toggleToolSection(bubble.dataset.toolTurnKey, bubble.dataset.defaultToolSection);
    };
  });
}
function updateConversationRenderMode(activeSession) {
  const drawer = document.getElementById('sessionDrawer');
  const drawerScroll = drawer.querySelector('.drawer-scroll');
  const conversation = drawer.querySelector('.conversation');
  if (!activeSession || !drawerScroll || !conversation) return;

  const maxBefore = Math.max(0, drawerScroll.scrollHeight - drawerScroll.clientHeight);
  const progress = maxBefore ? drawerScroll.scrollTop / maxBefore : 0;
  const visible = Number(conversation.dataset.visible || conversationLimit(activeSession));
  const turns = (activeSession.conversation || []).slice(0, visible);
  const key = sessionKey(activeSession);

  setMessageRenderButtons();
  conversation.innerHTML = turns.map((turn, index) => turnHtml(turn, index, key)).join('');
  bindToolTurnToggles(activeSession);

  window.requestAnimationFrame(() => {
    const maxAfter = Math.max(0, drawerScroll.scrollHeight - drawerScroll.clientHeight);
    drawerScroll.scrollTop = maxAfter ? progress * maxAfter : 0;
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
  conversation.insertAdjacentHTML('beforeend', nextTurns.map((turn, offset) => turnHtml(turn, current + offset, key)).join(''));
  conversation.dataset.visible = String(nextLimit);
  state.conversationLimits.set(key, nextLimit);
  bindToolTurnToggles(activeSession);

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
