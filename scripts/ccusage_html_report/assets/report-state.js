const DATA = JSON.parse(document.getElementById('report-data').textContent);
const metricLabels = DATA.metricLabels;
function initialStoredValue(key, fallback) {
  try {
    const value = window.localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch (_) {
    return fallback;
  }
}
function initialDrawerWidth() {
  const value = Number(initialStoredValue('ccusage.sessionDrawerWidth', 440));
  if (!Number.isFinite(value)) return 440;
  return Math.min(Math.max(value, 360), 1120);
}
const state = {
  activeTab: 'usage',
  period: 'daily',
  metric: 'totalTokens',
  selected: null,
  visible: new Set(['__total', ...(DATA.models || [])]),
  view: 'cards',
  sort: 'recent',
  query: '',
  filters: {agent: '', model: '', transcript: 'all', dateFrom: '', dateTo: ''},
  limit: 80,
  activeSessionKey: null,
  conversationBatch: 24,
  conversationLimits: new Map(),
  messageRenderMode: initialStoredValue('ccusage.messageRenderMode', 'raw') === 'markdown' ? 'markdown' : 'raw',
  drawerWidth: initialDrawerWidth()
};
const palette = ['#38bdf8', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316', '#0ea5e9', '#10b981'];
let barHits = [];
