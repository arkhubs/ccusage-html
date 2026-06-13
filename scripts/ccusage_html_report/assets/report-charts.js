function seriesColor(series, i) {
  if (series === '__total') return palette[0];
  const idx = Math.max(1, DATA.models.indexOf(series) + 1);
  return palette[idx % palette.length];
}
function seriesLabel(series) { return series === '__total' ? 'Total' : series; }
function bucketValue(bucket, series, metric = state.metric) {
  if (series === '__total') return Number(bucket[metric] || 0);
  return Number(((bucket.models || {})[series] || {})[metric] || 0);
}
function currentBuckets() { return DATA.periods[state.period] || []; }
function currentSeries() {
  return ['__total', ...(DATA.models || [])].filter(s => state.visible.has(s));
}
function renderMainTabs() {
  const tabs = [
    {id: 'usage', label: 'Usage'},
    {id: 'sessions', label: `Sessions (${fmt((DATA.sessions || []).length)})`}
  ];
  const el = document.getElementById('mainTabs');
  el.innerHTML = tabs.map(tab => `<button class="${state.activeTab === tab.id ? 'active' : ''}" data-tab="${tab.id}">${esc(tab.label)}</button>`).join('');
  el.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    state.activeTab = btn.dataset.tab;
    renderAll();
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.dataset.panel === state.activeTab);
  });
}
function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, rect.width) * dpr;
  canvas.height = Math.max(260, rect.height) * dpr;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {ctx, width: Math.max(320, rect.width), height: Math.max(260, rect.height)};
}
function drawGrid(ctx, x, y, w, h, max, formatter) {
  const formatValue = formatter || fmt;
  ctx.strokeStyle = '#243244';
  ctx.fillStyle = '#8fa1b8';
  ctx.font = '12px system-ui';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = y + h - h * (i / 4);
    ctx.beginPath();
    ctx.moveTo(x, yy);
    ctx.lineTo(x + w, yy);
    ctx.stroke();
    ctx.fillText(formatValue(max * i / 4), 8, yy + 4);
  }
}
function drawBarChart() {
  const canvas = document.getElementById('barChart');
  const {ctx, width, height} = setupCanvas(canvas);
  const pad = {l: 74, r: 20, t: 24, b: 64};
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const buckets = currentBuckets();
  const series = currentSeries();
  barHits = [];
  ctx.clearRect(0, 0, width, height);
  if (!buckets.length || !series.length) {
    ctx.fillStyle = '#8fa1b8';
    ctx.fillText('No data for this period.', pad.l, pad.t + 20);
    return;
  }
  const max = Math.max(1, ...buckets.flatMap(b => series.map(s => bucketValue(b, s))));
  drawGrid(ctx, pad.l, pad.t, plotW, plotH, max, value => metricFmt(state.metric, value));
  const groupW = plotW / buckets.length;
  const gap = 3;
  const barW = Math.max(2, Math.min(28, (groupW * 0.72) / series.length - gap));
  buckets.forEach((bucket, i) => {
    const totalW = series.length * barW + (series.length - 1) * gap;
    let x = pad.l + i * groupW + (groupW - totalW) / 2;
    series.forEach((s, j) => {
      const value = bucketValue(bucket, s);
      const h = plotH * value / max;
      const y = pad.t + plotH - h;
      const selected = state.selected && state.selected.period === state.period && state.selected.label === bucket.label;
      ctx.globalAlpha = state.selected && !selected ? .34 : 1;
      ctx.fillStyle = seriesColor(s, j);
      ctx.fillRect(x, y, barW, h);
      barHits.push({x, y, w: barW, h, label: bucket.label, series: s});
      x += barW + gap;
    });
    ctx.globalAlpha = 1;
    const showEvery = Math.max(1, Math.ceil(buckets.length / 12));
    if (i % showEvery === 0) {
      ctx.save();
      ctx.translate(pad.l + i * groupW + groupW / 2, pad.t + plotH + 18);
      ctx.rotate(-Math.PI / 7);
      ctx.fillStyle = '#8fa1b8';
      ctx.font = '12px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText(bucket.label, 0, 0);
      ctx.restore();
    }
  });
}
function drawLineChart() {
  const canvas = document.getElementById('lineChart');
  const {ctx, width, height} = setupCanvas(canvas);
  const pad = {l: 74, r: 20, t: 24, b: 56};
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const buckets = currentBuckets();
  const lineSeries = state.selected && state.selected.series !== '__total' ? state.selected.series : '__total';
  ctx.clearRect(0, 0, width, height);
  if (!buckets.length) {
    ctx.fillStyle = '#8fa1b8';
    ctx.fillText('No data for this period.', pad.l, pad.t + 20);
    return;
  }
  const values = buckets.map(b => bucketValue(b, lineSeries));
  const max = Math.max(1, ...values);
  drawGrid(ctx, pad.l, pad.t, plotW, plotH, max, value => metricFmt(state.metric, value));
  ctx.strokeStyle = seriesColor(lineSeries, 0);
  ctx.lineWidth = 3;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
    const y = pad.t + plotH - plotH * v / max;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  values.forEach((v, i) => {
    const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
    const y = pad.t + plotH - plotH * v / max;
    ctx.fillStyle = '#0b1220';
    ctx.strokeStyle = seriesColor(lineSeries, 0);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
  ctx.fillStyle = '#8fa1b8';
  ctx.font = '12px system-ui';
  ctx.fillText(seriesLabel(lineSeries) + ' / ' + metricLabels[state.metric], pad.l, 16);
}
function renderTabs() {
  const periodTabs = document.getElementById('periodTabs');
  periodTabs.innerHTML = ['daily', 'weekly', 'monthly'].map(p => `<button class="${state.period === p ? 'active' : ''}" data-period="${p}">${p[0].toUpperCase() + p.slice(1)}</button>`).join('');
  periodTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    state.period = btn.dataset.period;
    state.selected = null;
    renderAll();
  });
  const metricTabs = document.getElementById('metricTabs');
  metricTabs.innerHTML = Object.entries(metricLabels).map(([key, label]) => `<button class="${state.metric === key ? 'active' : ''}" data-metric="${key}">${label}</button>`).join('');
  metricTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    state.metric = btn.dataset.metric;
    renderAll();
  });
}
function renderLegend() {
  const legend = document.getElementById('legend');
  const series = ['__total', ...(DATA.models || [])];
  legend.innerHTML = series.map((s, i) => `<button class="chip ${s === '__total' ? 'total' : ''} ${state.visible.has(s) ? '' : 'off'}" data-series="${esc(s)}"><span style="color:${seriesColor(s, i)}">■</span> ${esc(seriesLabel(s))}</button>`).join('');
  legend.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    const s = btn.dataset.series;
    if (state.visible.has(s) && state.visible.size > 1) state.visible.delete(s);
    else state.visible.add(s);
    renderAll();
  });
}
function renderSelection() {
  const el = document.getElementById('selection');
  if (!state.selected) {
    el.innerHTML = '<span>Click a bar to filter sessions by bucket. Toggle legend chips to show or hide bars.</span>';
    return;
  }
  el.innerHTML = `<span class="pill">${esc(state.period)}: ${esc(state.selected.label)} / ${esc(seriesLabel(state.selected.series))}</span><button id="clearSelection">Clear filter</button>`;
  document.getElementById('clearSelection').onclick = () => { state.selected = null; renderAll(); };
}
