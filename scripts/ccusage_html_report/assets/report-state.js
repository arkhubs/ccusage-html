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
function normalizeTheme(value) {
  return value === 'light' ? 'light' : 'dark';
}
const state = {
  activeTab: 'usage',
  theme: normalizeTheme(initialStoredValue('ccusage.theme', document.documentElement.dataset.theme || 'dark')),
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
  expandedToolCalls: new Set(),
  expandedToolResults: new Set(),
  messageRenderMode: initialStoredValue('ccusage.messageRenderMode', 'raw') === 'markdown' ? 'markdown' : 'raw',
  drawerWidth: initialDrawerWidth()
};
const palette = ['#38bdf8', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316', '#0ea5e9', '#10b981'];
let barHits = [];
function applyTheme(theme) {
  state.theme = normalizeTheme(theme);
  document.documentElement.dataset.theme = state.theme;
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  const next = state.theme === 'light' ? 'dark' : 'light';
  toggle.dataset.nextTheme = next;
  const label = next === 'light' ? 'Switch to light mode' : 'Switch to dark mode';
  toggle.setAttribute('aria-label', label);
  toggle.setAttribute('title', label);
}
function setTheme(theme) {
  applyTheme(theme);
  try {
    window.localStorage.setItem('ccusage.theme', state.theme);
  } catch (_) {}
  if (state.activeTab === 'usage') {
    window.requestAnimationFrame(() => { drawBarChart(); drawLineChart(); });
  }
}
function setupThemeToggle() {
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  toggle.onclick = () => setTheme(state.theme === 'light' ? 'dark' : 'light');
  applyTheme(state.theme);
}
