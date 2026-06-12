from __future__ import annotations

import json
from typing import Any


def html_document(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ccusage report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1220;
      --panel: #111827;
      --panel-2: #0f172a;
      --line: #243244;
      --text: #e5edf6;
      --muted: #8fa1b8;
      --strong: #f8fafc;
      --accent: #14b8a6;
      --accent-2: #38bdf8;
      --warn: #f59e0b;
      --shadow: 0 18px 60px rgba(0, 0, 0, .32);
      --radius: 8px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      padding: 32px clamp(18px, 4vw, 56px) 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #0e1a2d 0%, #0b1220 100%);
    }}
    main {{ padding: 24px clamp(18px, 4vw, 56px) 48px; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 46px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 19px; letter-spacing: 0; }}
    .subhead {{ margin-top: 8px; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .stat, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .stat {{ padding: 16px; }}
    .stat .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .stat .value {{ margin-top: 6px; color: var(--strong); font-size: 26px; font-weight: 760; }}
    .main-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }}
    .main-tabs button {{
      min-width: 112px;
      min-height: 40px;
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .panel {{ padding: 20px; margin-bottom: 18px; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }}
    .tabs, .chips, .view-switch {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    input {{ min-width: 0; width: 100%; }}
    button, select, input {{
      border: 1px solid var(--line);
      background: #0b1628;
      color: var(--text);
      border-radius: 7px;
      padding: 8px 10px;
      font: inherit;
    }}
    button {{ cursor: pointer; }}
    button.active, button:hover {{ border-color: var(--accent); color: #ecfeff; }}
    .chip.off {{ opacity: .42; text-decoration: line-through; }}
    .chip.total {{ border-color: #38bdf8; }}
    .chart-wrap {{ position: relative; min-height: 360px; }}
    canvas {{ width: 100%; height: 360px; display: block; }}
    .selection {{
      min-height: 28px;
      color: var(--muted);
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--text);
      background: #0b1628;
    }}
    .side-card {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: var(--radius);
      padding: 14px;
      margin-bottom: 10px;
    }}
    .side-card .name {{ font-weight: 700; }}
    .side-card .bar {{ height: 8px; border-radius: 99px; background: #1f2937; overflow: hidden; margin-top: 10px; }}
    .side-card .bar span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }}
    .model-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .model-grid .side-card {{ margin-bottom: 0; }}
    .model-metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .price-strip {{
      border-top: 1px solid var(--line);
      margin-top: 12px;
      padding-top: 12px;
    }}
    .session-toolbar {{ align-items: flex-start; }}
    .session-toolbar h2 {{ margin-top: 8px; }}
    .session-controls {{
      display: grid;
      grid-template-columns: minmax(240px, 1fr) minmax(170px, auto) auto;
      gap: 8px;
      flex: 1 1 620px;
    }}
    .sessions.cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }}
    .session-card {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 18px;
      background: var(--panel-2);
      display: grid;
      gap: 14px;
      min-width: 0;
    }}
    .session-top {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
    }}
    .session-card h3 {{ margin: 0 0 8px; font-size: 17px; line-height: 1.35; color: var(--strong); }}
    .session-id {{
      max-width: 360px;
      overflow-wrap: anywhere;
      text-align: right;
    }}
    .session-metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
      gap: 8px 14px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 12px 0;
    }}
    .metric-mini .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .metric-mini .value {{ margin-top: 2px; color: var(--strong); font-size: 14px; font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }}
    .snippets {{ margin-top: 12px; display: grid; gap: 8px; }}
    .snippet {{
      border-left: 3px solid var(--accent);
      background: rgba(20, 184, 166, .08);
      padding: 8px 10px;
      border-radius: 6px;
      color: #dce8f5;
      font-size: 13px;
    }}
    .snippet.assistant {{ border-left-color: var(--accent-2); background: rgba(56, 189, 248, .08); }}
    .sessions.list {{ display: grid; gap: 8px; }}
    .sessions.list .session-card {{ grid-template-columns: minmax(280px, 1fr) minmax(320px, .8fr); align-items: start; }}
    .sessions.list .session-top {{ grid-column: 1 / -1; }}
    .sessions.list .session-metrics {{ grid-column: 1 / -1; }}
    .sessions.list .snippets {{ grid-column: 1 / -1; }}
    .sessions.list .session-detail {{ grid-column: 1 / -1; }}
    .detail-toggle {{
      justify-self: start;
      min-height: 36px;
    }}
    .session-detail {{
      display: grid;
      gap: 14px;
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
    }}
    .model-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .model-table th, .model-table td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: left;
      vertical-align: top;
    }}
    .model-table th {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .conversation {{
      display: grid;
      gap: 10px;
      max-height: 560px;
      overflow: auto;
      padding-right: 4px;
    }}
    .turn {{
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      border-radius: 6px;
      background: rgba(20, 184, 166, .06);
      padding: 10px;
    }}
    .turn.assistant {{ border-left-color: var(--accent-2); background: rgba(56, 189, 248, .06); }}
    .turn .text {{
      margin-top: 6px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #dce8f5;
      font-size: 13px;
    }}
    .load-row {{ margin-top: 16px; }}
    .muted {{ color: var(--muted); }}
    .footer-note {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 960px) {{
      .summary, .session-controls, .sessions.cards, .sessions.list .session-card {{ grid-template-columns: 1fr; }}
      .session-top {{ display: grid; }}
      .session-id {{ max-width: none; text-align: left; }}
      canvas {{ height: 320px; }}
      .chart-wrap {{ min-height: 320px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>ccusage report</h1>
    <div class="subhead" id="reportMeta"></div>
    <section class="summary" id="summary"></section>
  </header>
  <main>
    <nav class="main-tabs" id="mainTabs" aria-label="Report sections"></nav>
    <section class="tab-panel active" data-panel="usage">
      <div class="panel">
        <h2>Model mix</h2>
        <div id="modelMix" class="model-grid"></div>
        <div class="footer-note" id="modelPriceNote"></div>
      </div>
      <div class="panel">
        <div class="toolbar">
          <div class="tabs" id="periodTabs"></div>
          <div class="tabs" id="metricTabs"></div>
        </div>
        <div class="selection" id="selection"></div>
        <div class="chips" id="legend"></div>
        <div class="chart-wrap"><canvas id="barChart"></canvas></div>
      </div>
      <div class="panel">
        <h2>Usage curve</h2>
        <div class="chart-wrap"><canvas id="lineChart"></canvas></div>
      </div>
    </section>
    <section class="tab-panel" data-panel="sessions">
      <div class="panel">
        <div class="toolbar session-toolbar">
          <h2>Sessions</h2>
          <div class="session-controls">
            <input id="sessionSearch" placeholder="Search title, agent, model, or snippet">
            <select id="sessionSort">
              <option value="recent">Recent first</option>
              <option value="tokens">Tokens high to low</option>
              <option value="cost">Cost high to low</option>
              <option value="title">Title A to Z</option>
            </select>
            <div class="view-switch">
              <button id="cardsBtn" class="active">Cards</button>
              <button id="listBtn">List</button>
            </div>
          </div>
        </div>
        <div class="selection" id="sessionFilter"></div>
        <div class="muted" id="sessionCount"></div>
        <div id="sessions" class="sessions cards"></div>
        <div class="load-row"><button id="loadMore">Load more</button></div>
        <div class="footer-note" id="archiveNote">Generated as a standalone local HTML file. Embedded snippets may contain private conversation data.</div>
      </div>
    </section>
  </main>
  <script id="report-data" type="application/json">__REPORT_DATA_JSON__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('report-data').textContent);
    const metricLabels = DATA.metricLabels;
    const state = {{
      activeTab: 'usage',
      period: 'daily',
      metric: 'totalTokens',
      selected: null,
      visible: new Set(['__total', ...(DATA.models || [])]),
      view: 'cards',
      sort: 'recent',
      query: '',
      limit: 80,
      expanded: new Set()
    }};
    const palette = ['#38bdf8', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316', '#0ea5e9', '#10b981'];
    let barHits = [];

    function fmt(n) {{
      n = Number(n || 0);
      if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
      if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
      if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
      return String(Math.round(n));
    }}
    function money(n) {{
      if (n === undefined || n === null || Number.isNaN(Number(n))) return 'n/a';
      return '$' + Number(n).toFixed(2);
    }}
    function compactMoney(n) {{
      n = Number(n || 0);
      const sign = n < 0 ? '-' : '';
      const abs = Math.abs(n);
      if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
      if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
      if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(2) + 'K';
      return sign + '$' + abs.toFixed(2);
    }}
    function priceMoney(n) {{
      if (n === undefined || n === null || Number.isNaN(Number(n))) return 'n/a';
      const value = Number(n);
      if (Math.abs(value) >= 1) return '$' + value.toFixed(2);
      if (Math.abs(value) >= .01) return '$' + value.toFixed(3);
      return '$' + value.toFixed(4);
    }}
    function metricFmt(metric, value) {{
      return metric === 'costUSD' ? compactMoney(value) : fmt(value);
    }}
    function esc(s) {{
      return String(s ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    }}
    function seriesColor(series, i) {{
      if (series === '__total') return palette[0];
      const idx = Math.max(1, DATA.models.indexOf(series) + 1);
      return palette[idx % palette.length];
    }}
    function seriesLabel(series) {{ return series === '__total' ? 'Total' : series; }}
    function bucketValue(bucket, series, metric = state.metric) {{
      if (series === '__total') return Number(bucket[metric] || 0);
      return Number(((bucket.models || {{}})[series] || {{}})[metric] || 0);
    }}
    function currentBuckets() {{ return DATA.periods[state.period] || []; }}
    function currentSeries() {{
      return ['__total', ...(DATA.models || [])].filter(s => state.visible.has(s));
    }}
    function renderMainTabs() {{
      const tabs = [
        {{id: 'usage', label: 'Usage'}},
        {{id: 'sessions', label: `Sessions (${fmt((DATA.sessions || []).length)})`}}
      ];
      const el = document.getElementById('mainTabs');
      el.innerHTML = tabs.map(tab => `<button class="${state.activeTab === tab.id ? 'active' : ''}" data-tab="${tab.id}">${esc(tab.label)}</button>`).join('');
      el.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        state.activeTab = btn.dataset.tab;
        renderAll();
      }});
      document.querySelectorAll('.tab-panel').forEach(panel => {{
        panel.classList.toggle('active', panel.dataset.panel === state.activeTab);
      }});
    }}
    function setupCanvas(canvas) {{
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(320, rect.width) * dpr;
      canvas.height = Math.max(260, rect.height) * dpr;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return {{ctx, width: Math.max(320, rect.width), height: Math.max(260, rect.height)}};
    }}
    function drawGrid(ctx, x, y, w, h, max, formatter) {{
      const formatValue = formatter || fmt;
      ctx.strokeStyle = '#243244';
      ctx.fillStyle = '#8fa1b8';
      ctx.font = '12px system-ui';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {{
        const yy = y + h - h * (i / 4);
        ctx.beginPath();
        ctx.moveTo(x, yy);
        ctx.lineTo(x + w, yy);
        ctx.stroke();
        ctx.fillText(formatValue(max * i / 4), 8, yy + 4);
      }}
    }}
    function drawBarChart() {{
      const canvas = document.getElementById('barChart');
      const {{ctx, width, height}} = setupCanvas(canvas);
      const pad = {{l: 74, r: 20, t: 24, b: 64}};
      const plotW = width - pad.l - pad.r;
      const plotH = height - pad.t - pad.b;
      const buckets = currentBuckets();
      const series = currentSeries();
      barHits = [];
      ctx.clearRect(0, 0, width, height);
      if (!buckets.length || !series.length) {{
        ctx.fillStyle = '#8fa1b8';
        ctx.fillText('No data for this period.', pad.l, pad.t + 20);
        return;
      }}
      const max = Math.max(1, ...buckets.flatMap(b => series.map(s => bucketValue(b, s))));
      drawGrid(ctx, pad.l, pad.t, plotW, plotH, max, value => metricFmt(state.metric, value));
      const groupW = plotW / buckets.length;
      const gap = 3;
      const barW = Math.max(2, Math.min(28, (groupW * 0.72) / series.length - gap));
      buckets.forEach((bucket, i) => {{
        const totalW = series.length * barW + (series.length - 1) * gap;
        let x = pad.l + i * groupW + (groupW - totalW) / 2;
        series.forEach((s, j) => {{
          const value = bucketValue(bucket, s);
          const h = plotH * value / max;
          const y = pad.t + plotH - h;
          const selected = state.selected && state.selected.period === state.period && state.selected.label === bucket.label;
          ctx.globalAlpha = state.selected && !selected ? .34 : 1;
          ctx.fillStyle = seriesColor(s, j);
          ctx.fillRect(x, y, barW, h);
          barHits.push({{x, y, w: barW, h, label: bucket.label, series: s}});
          x += barW + gap;
        }});
        ctx.globalAlpha = 1;
        const showEvery = Math.max(1, Math.ceil(buckets.length / 12));
        if (i % showEvery === 0) {{
          ctx.save();
          ctx.translate(pad.l + i * groupW + groupW / 2, pad.t + plotH + 18);
          ctx.rotate(-Math.PI / 7);
          ctx.fillStyle = '#8fa1b8';
          ctx.font = '12px system-ui';
          ctx.textAlign = 'right';
          ctx.fillText(bucket.label, 0, 0);
          ctx.restore();
        }}
      }});
    }}
    function drawLineChart() {{
      const canvas = document.getElementById('lineChart');
      const {{ctx, width, height}} = setupCanvas(canvas);
      const pad = {{l: 74, r: 20, t: 24, b: 56}};
      const plotW = width - pad.l - pad.r;
      const plotH = height - pad.t - pad.b;
      const buckets = currentBuckets();
      const lineSeries = state.selected && state.selected.series !== '__total' ? state.selected.series : '__total';
      ctx.clearRect(0, 0, width, height);
      if (!buckets.length) {{
        ctx.fillStyle = '#8fa1b8';
        ctx.fillText('No data for this period.', pad.l, pad.t + 20);
        return;
      }}
      const values = buckets.map(b => bucketValue(b, lineSeries));
      const max = Math.max(1, ...values);
      drawGrid(ctx, pad.l, pad.t, plotW, plotH, max, value => metricFmt(state.metric, value));
      ctx.strokeStyle = seriesColor(lineSeries, 0);
      ctx.lineWidth = 3;
      ctx.beginPath();
      values.forEach((v, i) => {{
        const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
        const y = pad.t + plotH - plotH * v / max;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
      values.forEach((v, i) => {{
        const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
        const y = pad.t + plotH - plotH * v / max;
        ctx.fillStyle = '#0b1220';
        ctx.strokeStyle = seriesColor(lineSeries, 0);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }});
      ctx.fillStyle = '#8fa1b8';
      ctx.font = '12px system-ui';
      ctx.fillText(seriesLabel(lineSeries) + ' / ' + metricLabels[state.metric], pad.l, 16);
    }}
    function renderTabs() {{
      const periodTabs = document.getElementById('periodTabs');
      periodTabs.innerHTML = ['daily', 'weekly', 'monthly'].map(p => `<button class="${state.period === p ? 'active' : ''}" data-period="${p}">${p[0].toUpperCase() + p.slice(1)}</button>`).join('');
      periodTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        state.period = btn.dataset.period;
        state.selected = null;
        renderAll();
      }});
      const metricTabs = document.getElementById('metricTabs');
      metricTabs.innerHTML = Object.entries(metricLabels).map(([key, label]) => `<button class="${state.metric === key ? 'active' : ''}" data-metric="${key}">${label}</button>`).join('');
      metricTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        state.metric = btn.dataset.metric;
        renderAll();
      }});
    }}
    function renderLegend() {{
      const legend = document.getElementById('legend');
      const series = ['__total', ...(DATA.models || [])];
      legend.innerHTML = series.map((s, i) => `<button class="chip ${s === '__total' ? 'total' : ''} ${state.visible.has(s) ? '' : 'off'}" data-series="${esc(s)}"><span style="color:${seriesColor(s, i)}">■</span> ${esc(seriesLabel(s))}</button>`).join('');
      legend.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        const s = btn.dataset.series;
        if (state.visible.has(s) && state.visible.size > 1) state.visible.delete(s);
        else state.visible.add(s);
        renderAll();
      }});
    }}
    function renderSelection() {{
      const el = document.getElementById('selection');
      if (!state.selected) {{
        el.innerHTML = '<span>Click a bar to filter sessions by bucket. Toggle legend chips to show or hide bars.</span>';
        return;
      }}
      el.innerHTML = `<span class="pill">${esc(state.period)}: ${esc(state.selected.label)} / ${esc(seriesLabel(state.selected.series))}</span><button id="clearSelection">Clear filter</button>`;
      document.getElementById('clearSelection').onclick = () => {{ state.selected = null; renderAll(); }};
    }}
    function renderSessionFilter() {{
      const el = document.getElementById('sessionFilter');
      if (!state.selected) {{
        el.innerHTML = '';
        return;
      }}
      el.innerHTML = `<span class="pill">Filtered by ${esc(state.period)}: ${esc(state.selected.label)} / ${esc(seriesLabel(state.selected.series))}</span><button id="clearSessionFilter">Clear filter</button>`;
      document.getElementById('clearSessionFilter').onclick = () => {{ state.selected = null; renderAll(); }};
    }}
    function bucketMatchesSession(s) {{
      if (!state.selected) return true;
      const key = state.period === 'daily' ? 'date' : state.period === 'weekly' ? 'week' : 'month';
      if (String(s[key] || '') !== state.selected.label) return false;
      if (state.selected.series !== '__total' && !(s.modelNames || []).includes(state.selected.series)) return false;
      return true;
    }}
    function filteredSessions() {{
      const q = state.query.toLowerCase();
      let sessions = (DATA.sessions || []).filter(bucketMatchesSession);
      if (q) {{
        sessions = sessions.filter(s => {{
          const hay = [
            s.title,
            s.agentName,
            s.sessionId,
            s.sessionFile,
            s.transcriptPath,
            ...(s.modelNames || []),
            ...((s.snippets || []).map(x => x.text)),
            ...((s.conversation || []).map(x => x.text))
          ].join(' ').toLowerCase();
          return hay.includes(q);
        }});
      }}
      sessions.sort((a, b) => {{
        if (state.sort === 'tokens') return Number(b.totalTokens || 0) - Number(a.totalTokens || 0);
        if (state.sort === 'cost') return Number(b.costUSD || 0) - Number(a.costUSD || 0);
        if (state.sort === 'title') return String(a.title || '').localeCompare(String(b.title || ''));
        return String(b.lastActivity || '').localeCompare(String(a.lastActivity || ''));
      }});
      return sessions;
    }}
    function sessionKey(s) {{
      return String(s.reportSessionId || s.sessionId || s.sessionFile || s.title || '');
    }}
    function metricBlock(label, value) {{
      return `<div class="metric-mini"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
    }}
    function modelPrice(model) {{
      return (((DATA.modelPrices || {{}}).models || {{}})[model]) || null;
    }}
    function priceBlocks(price) {{
      if (!price || price.source === 'unavailable') {{
        return '<div class="price-strip muted">Current price unavailable.</div>';
      }}
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
    }}
    function modelRows(models) {{
      const entries = Object.entries(models || {{}});
      if (!entries.length) return '<div class="muted">No per-model breakdown available.</div>';
      return `<table class="model-table">
        <thead><tr><th>Model</th><th>Total</th><th>Input</th><th>Output</th><th>Reasoning</th><th>Cache</th><th>Context</th><th>Cost</th></tr></thead>
        <tbody>${entries.map(([name, m]) => `<tr>
          <td>${esc(name)}</td>
          <td>${fmt(m.totalTokens)}</td>
          <td>${fmt(m.inputTokens)}</td>
          <td>${fmt(m.outputTokens)}</td>
          <td>${fmt(m.reasoningOutputTokens)}</td>
          <td>${fmt(Number(m.cacheCreationTokens || 0) + Number(m.cacheReadTokens || 0))}</td>
          <td>${fmt(m.contextTokens)}</td>
          <td>${money(m.costUSD)}</td>
        </tr>`).join('')}</tbody>
      </table>`;
    }}
    function conversationHtml(s) {{
      const turns = s.conversation || [];
      if (!turns.length) {{
        return '<div class="muted">No full transcript available for this session. Codex sessions include full local conversation when the JSONL file can be located.</div>';
      }}
      return `<div class="conversation">${turns.map(turn => `<div class="turn ${turn.role === 'assistant' ? 'assistant' : ''}">
        <div class="meta"><b>${esc(turn.role)}</b><span>${esc(turn.time || '')}</span><span>${fmt(turn.chars)} chars</span></div>
        <div class="text">${esc(turn.text)}</div>
      </div>`).join('')}</div>`;
    }}
    function sessionDetailHtml(s) {{
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
      return `<div class="session-detail">
        <div class="detail-grid">${detailMetrics}</div>
        <div>
          <h3>Models</h3>
          ${modelRows(s.models)}
        </div>
        <div>
          <h3>Conversation</h3>
          ${conversationHtml(s)}
        </div>
        ${s.transcriptPath ? `<div class="meta">Transcript: ${esc(s.transcriptPath)}</div>` : ''}
      </div>`;
    }}
    function sessionHtml(s) {{
      const snippets = (s.snippets || []).slice(0, 4).map(sn => `<div class="snippet ${sn.role === 'assistant' ? 'assistant' : ''}"><b>${esc(sn.role)}:</b> ${esc(sn.text)}</div>`).join('');
      const models = (s.modelNames || []).join(', ') || 'model n/a';
      const key = sessionKey(s);
      const isExpanded = state.expanded.has(key);
      const metrics = [
        ['Total', fmt(s.totalTokens)],
        ['Input', fmt(s.inputTokens)],
        ['Output', fmt(s.outputTokens)],
        ['Reasoning', fmt(s.reasoningOutputTokens)],
        ['Context', fmt(s.contextTokens)],
        ['Cost', money(s.costUSD)]
      ].map(([label, value]) => `<div class="metric-mini"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
      return `<article class="session-card">
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
        <button class="detail-toggle" data-session-key="${esc(key)}">${isExpanded ? 'Hide details' : 'Show details'}</button>
        ${isExpanded ? sessionDetailHtml(s) : ''}
      </article>`;
    }}
    function renderSessions() {{
      const sessions = filteredSessions();
      const count = document.getElementById('sessionCount');
      count.textContent = `${sessions.length} matching session${sessions.length === 1 ? '' : 's'}`;
      const container = document.getElementById('sessions');
      container.className = 'sessions ' + state.view;
      document.getElementById('cardsBtn').classList.toggle('active', state.view === 'cards');
      document.getElementById('listBtn').classList.toggle('active', state.view === 'list');
      container.innerHTML = sessions.slice(0, state.limit).map(sessionHtml).join('');
      container.querySelectorAll('.detail-toggle').forEach(btn => btn.onclick = () => {{
        const key = btn.dataset.sessionKey;
        if (state.expanded.has(key)) state.expanded.delete(key);
        else state.expanded.add(key);
        renderSessions();
      }});
      document.getElementById('loadMore').style.display = sessions.length > state.limit ? 'inline-flex' : 'none';
    }}
    function renderSummary() {{
      const t = DATA.totals || {{}};
      const sessions = DATA.sessions || [];
      const summary = [
        ['Total tokens', fmt(t.totalTokens)],
        ['Cost', money(t.costUSD)],
        ['Input / Output', `${fmt(t.inputTokens)} / ${fmt(t.outputTokens)}`],
        ['Reasoning', fmt(t.reasoningOutputTokens)],
        ['Sessions', fmt(sessions.length)]
      ];
      document.getElementById('summary').innerHTML = summary.map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
      const filters = DATA.filters || {{}};
      const range = [filters.since, filters.until].filter(Boolean).join(' to ') || 'all available dates';
      const agentLabel = DATA.agentInput && DATA.agentInput !== DATA.agent ? `${DATA.agentInput} -> ${DATA.agent}` : DATA.agent;
      document.getElementById('reportMeta').textContent = `${agentLabel} usage, ${range}. Generated ${DATA.generatedAt}.`;
    }}
    function renderArchiveNote() {{
      const archive = DATA.archive || {{}};
      const lines = ['Generated as a standalone local HTML file. Embedded snippets may contain private conversation data.'];
      if (archive.url) lines.push('URL: ' + archive.url);
      if (archive.htmlPath) lines.push('HTML: ' + archive.htmlPath);
      if (archive.directory) lines.push('Archive: ' + archive.directory);
      document.getElementById('archiveNote').innerHTML = lines.map(esc).join('<br>');
    }}
    function renderModelPriceNote() {{
      const pricing = DATA.modelPrices || {{}};
      const sources = pricing.sources || [];
      const ok = sources.filter(s => s.status === 'ok').map(s => s.name).join(', ');
      const unavailable = (DATA.models || []).filter(model => {{
        const price = modelPrice(model);
        return !price || price.source === 'unavailable';
      }});
      const lines = [];
      if (ok) lines.push('Model prices are best-effort current rates fetched from: ' + ok + '.');
      else lines.push('Model prices are unavailable for this report.');
      if (unavailable.length) lines.push('No price match for: ' + unavailable.join(', ') + '.');
      lines.push('Per-model costs are estimated from these rates when ccusage does not provide model-level cost.');
      lines.push('Price unit: USD per 1M tokens. Cache hit means cached input/cache read.');
      document.getElementById('modelPriceNote').innerHTML = lines.map(esc).join('<br>');
    }}
    function renderModelMix() {{
      const models = DATA.models || [];
      const totals = new Map(models.map(m => [m, {{
        totalTokens: 0,
        inputTokens: 0,
        outputTokens: 0,
        reasoningOutputTokens: 0,
        cacheCreationTokens: 0,
        cacheReadTokens: 0,
        contextTokens: 0,
        generationTokens: 0,
        costUSD: null
      }}]));
      function addUsage(target, source) {{
        target.totalTokens += Number(source.totalTokens || 0);
        target.inputTokens += Number(source.inputTokens || 0);
        target.outputTokens += Number(source.outputTokens || 0);
        target.reasoningOutputTokens += Number(source.reasoningOutputTokens || 0);
        target.cacheCreationTokens += Number(source.cacheCreationTokens || 0);
        target.cacheReadTokens += Number(source.cacheReadTokens || 0);
        target.contextTokens += Number(source.contextTokens || 0);
        target.generationTokens += Number(source.generationTokens || 0);
        if (source.costUSD !== undefined && source.costUSD !== null && !Number.isNaN(Number(source.costUSD))) {{
          target.costUSD = Number(target.costUSD || 0) + Number(source.costUSD);
        }}
      }}
      (DATA.periods.daily || []).forEach(bucket => {{
        models.forEach(model => addUsage(totals.get(model), (bucket.models || {{}})[model] || {{}}));
      }});
      const max = Math.max(1, ...Array.from(totals.values()).map(t => t.totalTokens));
      document.getElementById('modelMix').innerHTML = models.length ? models.map(model => `
        <div class="side-card">
          <div class="name">${esc(model)}</div>
          <div class="meta">${fmt(totals.get(model).totalTokens)} tokens · ${money(totals.get(model).costUSD)}</div>
          <div class="model-metrics">
            ${[
              ['Total', fmt(totals.get(model).totalTokens)],
              ['Input', fmt(totals.get(model).inputTokens)],
              ['Output', fmt(totals.get(model).outputTokens)],
              ['Reasoning', fmt(totals.get(model).reasoningOutputTokens)],
              ['Context', fmt(totals.get(model).contextTokens)],
              ['Cost', money(totals.get(model).costUSD)]
            ].map(([label, value]) => `<div class="metric-mini"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('')}
          </div>
          ${priceBlocks(modelPrice(model))}
          <div class="bar"><span style="width:${Math.max(2, 100 * totals.get(model).totalTokens / max)}%"></span></div>
        </div>`).join('') : '<div class="muted">No model data found.</div>';
      renderModelPriceNote();
    }}
    function renderAll() {{
      renderMainTabs();
      renderSummary();
      renderTabs();
      renderLegend();
      renderSelection();
      renderSessionFilter();
      renderModelMix();
      renderSessions();
      renderArchiveNote();
      if (state.activeTab === 'usage') {{
        window.requestAnimationFrame(() => {{ drawBarChart(); drawLineChart(); }});
      }}
    }}
    document.getElementById('barChart').addEventListener('click', event => {{
      const rect = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = barHits.find(h => x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h);
      if (!hit) return;
      const same = state.selected && state.selected.period === state.period && state.selected.label === hit.label && state.selected.series === hit.series;
      state.selected = same ? null : {{period: state.period, label: hit.label, series: hit.series}};
      renderAll();
    }});
    document.getElementById('sessionSearch').addEventListener('input', event => {{
      state.query = event.target.value;
      state.limit = 80;
      renderSessions();
    }});
    document.getElementById('sessionSort').addEventListener('change', event => {{
      state.sort = event.target.value;
      renderSessions();
    }});
    document.getElementById('cardsBtn').onclick = () => {{
      state.view = 'cards';
      document.getElementById('cardsBtn').classList.add('active');
      document.getElementById('listBtn').classList.remove('active');
      renderSessions();
    }};
    document.getElementById('listBtn').onclick = () => {{
      state.view = 'list';
      document.getElementById('listBtn').classList.add('active');
      document.getElementById('cardsBtn').classList.remove('active');
      renderSessions();
    }};
    document.getElementById('loadMore').onclick = () => {{
      state.limit += 80;
      renderSessions();
    }};
    window.addEventListener('resize', () => {{
      window.clearTimeout(window.__ccusageResize);
      window.__ccusageResize = window.setTimeout(() => {{
        if (state.activeTab === 'usage') {{ drawBarChart(); drawLineChart(); }}
      }}, 120);
    }});
    renderAll();
  </script>
</body>
</html>
"""
    template = template.replace("{{", "{").replace("}}", "}")
    return template.replace("__REPORT_DATA_JSON__", data_json)
