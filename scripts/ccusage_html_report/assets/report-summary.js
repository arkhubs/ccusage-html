function renderSummary() {
  const t = DATA.totals || {};
  const sessions = DATA.sessions || [];
  const summary = [
    ['Total tokens', fmt(t.totalTokens)],
    ['Cost', money(t.costUSD)],
    ['Input / Output', `${fmt(t.inputTokens)} / ${fmt(t.outputTokens)}`],
    ['Reasoning', fmt(t.reasoningOutputTokens)],
    ['Sessions', fmt(sessions.length)]
  ];
  document.getElementById('summary').innerHTML = summary.map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
  const filters = DATA.filters || {};
  const range = [filters.since, filters.until].filter(Boolean).join(' to ') || 'all available dates';
  const agentLabel = DATA.agentInput && DATA.agentInput !== DATA.agent ? `${DATA.agentInput} -> ${DATA.agent}` : DATA.agent;
  document.getElementById('reportMeta').textContent = `${agentLabel} usage, ${range}. Generated ${DATA.generatedAt}.`;
}
function renderArchiveNote() {
  const archive = DATA.archive || {};
  const lines = ['Generated as a standalone local HTML file. Embedded snippets may contain private conversation data.'];
  if (archive.url) lines.push('URL: ' + archive.url);
  if (archive.htmlPath) lines.push('HTML: ' + archive.htmlPath);
  if (archive.directory) lines.push('Archive: ' + archive.directory);
  document.getElementById('archiveNote').innerHTML = lines.map(esc).join('<br>');
}
function renderModelPriceNote() {
  const pricing = DATA.modelPrices || {};
  const sources = pricing.sources || [];
  const ok = sources.filter(s => s.status === 'ok').map(s => s.name).join(', ');
  const unavailable = (DATA.models || []).filter(model => {
    const price = modelPrice(model);
    return !price || price.source === 'unavailable';
  });
  const lines = [];
  if (ok) lines.push('Model prices are best-effort current rates fetched from: ' + ok + '.');
  else lines.push('Model prices are unavailable for this report.');
  if (unavailable.length) lines.push('No price match for: ' + unavailable.join(', ') + '.');
  lines.push('Per-model costs are estimated from these rates when ccusage does not provide model-level cost.');
  lines.push('Price unit: USD per 1M tokens. Cache hit means cached input/cache read.');
  document.getElementById('modelPriceNote').innerHTML = lines.map(esc).join('<br>');
}
function renderModelMix() {
  const models = DATA.models || [];
  const totals = new Map(models.map(m => [m, {
    totalTokens: 0,
    inputTokens: 0,
    outputTokens: 0,
    reasoningOutputTokens: 0,
    cacheCreationTokens: 0,
    cacheReadTokens: 0,
    contextTokens: 0,
    generationTokens: 0,
    costUSD: null
  }]));
  function addUsage(target, source) {
    target.totalTokens += Number(source.totalTokens || 0);
    target.inputTokens += Number(source.inputTokens || 0);
    target.outputTokens += Number(source.outputTokens || 0);
    target.reasoningOutputTokens += Number(source.reasoningOutputTokens || 0);
    target.cacheCreationTokens += Number(source.cacheCreationTokens || 0);
    target.cacheReadTokens += Number(source.cacheReadTokens || 0);
    target.contextTokens += Number(source.contextTokens || 0);
    target.generationTokens += Number(source.generationTokens || 0);
    if (source.costUSD !== undefined && source.costUSD !== null && !Number.isNaN(Number(source.costUSD))) {
      target.costUSD = Number(target.costUSD || 0) + Number(source.costUSD);
    }
  }
  (DATA.periods.daily || []).forEach(bucket => {
    models.forEach(model => addUsage(totals.get(model), (bucket.models || {})[model] || {}));
  });
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
}
