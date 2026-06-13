function setupSessionFilterOptions() {
  const sessions = DATA.sessions || [];
  const agents = uniqueSorted(sessions.map(s => s.agentName || DATA.agent));
  const models = uniqueSorted([...(DATA.models || []), ...sessions.flatMap(s => s.modelNames || [])]);
  document.getElementById('sessionAgent').innerHTML = optionHtml('All agents') + agents.map(agent => optionHtml(agent, agent)).join('');
  document.getElementById('sessionModel').innerHTML = optionHtml('All models') + models.map(model => optionHtml(model, model)).join('');
}
function syncSessionFilterInputs() {
  document.getElementById('sessionSearch').value = state.query;
  document.getElementById('sessionSort').value = state.sort;
  document.getElementById('sessionAgent').value = state.filters.agent;
  document.getElementById('sessionModel').value = state.filters.model;
  document.getElementById('sessionTranscript').value = state.filters.transcript;
  document.getElementById('sessionFrom').value = state.filters.dateFrom;
  document.getElementById('sessionTo').value = state.filters.dateTo;
}
function resetSessionPaging() {
  state.limit = 80;
  state.activeSessionKey = null;
}
function clearSessionFilters() {
  state.selected = null;
  state.query = '';
  state.filters = {agent: '', model: '', transcript: 'all', dateFrom: '', dateTo: ''};
  resetSessionPaging();
  syncSessionFilterInputs();
  renderAll();
}
function sessionTime(s) {
  return Number(s.sortTime || 0);
}
function compareTitle(a, b) {
  return String(a.title || a.reportSessionId || '').localeCompare(String(b.title || b.reportSessionId || ''));
}
function hasTranscript(s) {
  return Boolean((s.conversation || []).length || s.transcriptPath);
}
function sessionMatchesManualFilters(s) {
  const filters = state.filters;
  if (filters.agent && String(s.agentName || DATA.agent || '') !== filters.agent) return false;
  if (filters.model && !(s.modelNames || []).includes(filters.model)) return false;
  if (filters.transcript === 'with' && !hasTranscript(s)) return false;
  if (filters.transcript === 'without' && hasTranscript(s)) return false;
  const date = String(s.date || '');
  if (filters.dateFrom && (!date || date === 'Unknown' || date < filters.dateFrom)) return false;
  if (filters.dateTo && (!date || date === 'Unknown' || date > filters.dateTo)) return false;
  return true;
}
function applySessionFiltersChanged() {
  resetSessionPaging();
  renderSessionFilter();
  renderSessions();
}
