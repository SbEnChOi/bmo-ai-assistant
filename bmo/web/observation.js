'use strict';
(() => {
  const el = id => document.getElementById(id);
  let current = null, saving = false;
  function update(data) {
    if (!data) return;
    current = data;
    if (!saving) {
      el('observe-enabled').checked = data.enabled;
      el('observe-proactive').checked = data.proactive;
    }
    el('observe-enabled').disabled = saving || !data.available;
    el('observe-proactive').disabled = saving || !data.available || !data.enabled;
    el('observe-status').textContent = !data.available ? '파이 카메라를 연결하면 사용할 수 있어요.'
      : !data.enabled ? '자동 관찰 꺼짐' : data.error || (!data.fresh ? '카메라 확인 중…'
      : `${data.analyzing ? '주변 분석 중' : '주변 관찰 중'} · 분석 ${data.analyses_hour || 0}/30회/시간 · 기억 ${data.memory_count}개 · 먼저 말하기 ${data.notices_hour}회/시간`);
    if(el('observe-summary'))el('observe-summary').textContent = data.enabled && data.summary
      ? `최근 상황: ${data.summary} · ${data.summary_age_seconds ?? '—'}초 전` : '최근 상황 분석을 기다리고 있어요.';
  }
  async function save() {
    if (saving || !current) return;
    const body = {enabled:el('observe-enabled').checked, proactive:el('observe-proactive').checked};
    saving = true; update(current);
    let failure = '';
    try {
      current = await (window.BmoPhone || window.BmoAdmin).api('observation', body);
      window.BmoPhone?.observationChanged?.(current);
      void window.BmoAdmin?.refresh();
    }
    catch (error) { failure = error.message; }
    finally { saving = false; update(current); if (failure) el('observe-status').textContent = failure; }
  }
  el('observe-enabled').onchange = save;
  el('observe-proactive').onchange = save;
  window.BmoObservation = {update};
  const state = (window.BmoPhone || window.BmoAdmin)?.state();
  if (state?.observation) update(state.observation);
})();
