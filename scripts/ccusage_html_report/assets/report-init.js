function renderAll() {
  renderMainTabs();
  renderSummary();
  renderTabs();
  renderLegend();
  renderSelection();
  renderSessionFilter();
  renderModelMix();
  renderSessions();
  renderArchiveNote();
  if (state.activeTab === 'usage') {
    window.requestAnimationFrame(() => { drawBarChart(); drawLineChart(); });
  }
}
document.getElementById('barChart').addEventListener('click', event => {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const hit = barHits.find(h => x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h);
  if (!hit) return;
  const same = state.selected && state.selected.period === state.period && state.selected.label === hit.label && state.selected.series === hit.series;
  state.selected = same ? null : {period: state.period, label: hit.label, series: hit.series};
  renderAll();
});
document.getElementById('sessionSearch').addEventListener('input', event => {
  state.query = event.target.value;
  resetSessionPaging();
  renderSessionFilter();
  renderSessions();
});
document.getElementById('sessionSort').addEventListener('change', event => {
  state.sort = event.target.value;
  resetSessionPaging();
  renderSessions();
});
document.getElementById('sessionAgent').addEventListener('change', event => {
  state.filters.agent = event.target.value;
  applySessionFiltersChanged();
});
document.getElementById('sessionModel').addEventListener('change', event => {
  state.filters.model = event.target.value;
  applySessionFiltersChanged();
});
document.getElementById('sessionTranscript').addEventListener('change', event => {
  state.filters.transcript = event.target.value;
  applySessionFiltersChanged();
});
document.getElementById('sessionFrom').addEventListener('change', event => {
  state.filters.dateFrom = event.target.value;
  applySessionFiltersChanged();
});
document.getElementById('sessionTo').addEventListener('change', event => {
  state.filters.dateTo = event.target.value;
  applySessionFiltersChanged();
});
document.getElementById('cardsBtn').onclick = () => {
  state.view = 'cards';
  document.getElementById('cardsBtn').classList.add('active');
  document.getElementById('listBtn').classList.remove('active');
  renderSessions();
};
document.getElementById('listBtn').onclick = () => {
  state.view = 'list';
  document.getElementById('listBtn').classList.add('active');
  document.getElementById('cardsBtn').classList.remove('active');
  renderSessions();
};
document.getElementById('loadMore').onclick = () => {
  appendSessionCards();
};
window.addEventListener('resize', () => {
  window.clearTimeout(window.__ccusageResize);
  window.__ccusageResize = window.setTimeout(() => {
    if (state.activeTab === 'usage') { drawBarChart(); drawLineChart(); }
  }, 120);
});
setupSessionFilterOptions();
syncSessionFilterInputs();
setupSessionDrawerResize();
renderAll();
