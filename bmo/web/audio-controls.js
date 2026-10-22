'use strict';
(() => {
  const el = id => document.getElementById(id), panel = document.querySelector('.realtime-panel');
  const devices = ['speaker', 'microphone'], pending = new Map(), confirmed = {};
  let saving = false, loading = false;
  const timers = {};
  function show(device, data) {
    const available = !!data?.available;
    for (const suffix of ['volume','down','up']) el(`${device}-${suffix}`).disabled = !available;
    if (available) {
      confirmed[device] = data.volume;
      el(`${device}-volume`).value = data.volume;
      el(`${device}-level`).textContent = `${data.volume}%${data.muted ? ' · 음소거' : ''}`;
    } else el(`${device}-level`).textContent = '연결 없음';
  }
  async function load() {
    if (loading || saving || pending.size) return;
    loading = true; el('audio-settings-status').textContent = '현재 음량 확인 중…';
    try {
      const response = await fetch('/api/audio-levels');
      if (!response.ok) throw Error('음량을 가져오지 못했어요. 설정을 다시 열어 주세요.');
      const data = await response.json(); devices.forEach(device => show(device, data[device]));
      el('audio-settings-status').textContent = devices.some(device => data[device]?.available) ? '파이 장치 음량 · 대화 중에도 조절할 수 있어요.' : '파이에서 USB 마이크와 스피커를 연결해 주세요.';
    } catch (error) { el('audio-settings-status').textContent = error.message; }
    finally { loading = false; }
  }
  async function save() {
    if (saving) return;
    saving = true;
    let failed = false;
    while (pending.size) {
      const [device, volume] = pending.entries().next().value; pending.delete(device);
      el('audio-settings-status').textContent = '음량 적용 중…';
      try {
        const data = await window.BmoPhone.api('audio-levels', {device, volume});
        confirmed[device] = data[device].volume;
        if (!pending.has(device) && Number(el(`${device}-volume`).value) === volume) show(device, data[device]);
      } catch (error) {
        failed = true; el('audio-settings-status').textContent = error.message;
        if (!pending.has(device) && Number(el(`${device}-volume`).value) === volume && confirmed[device] != null) {
          el(`${device}-volume`).value = confirmed[device];
          el(`${device}-level`).textContent = `${confirmed[device]}%`;
        }
      }
    }
    saving = false;
    if (!failed) el('audio-settings-status').textContent = '음량을 적용했어요.';
  }
  function change(device, value, immediate = false) {
    const volume = Math.max(0, Math.min(100, Math.round(Number(value))));
    if (!Number.isFinite(volume) || el(`${device}-volume`).disabled) return;
    el(`${device}-volume`).value = volume; el(`${device}-level`).textContent = `${volume}%`;
    clearTimeout(timers[device]);
    const queue = () => { pending.set(device, volume); void save(); };
    if (immediate) queue(); else timers[device] = setTimeout(queue, 200);
  }
  for (const device of devices) {
    el(`${device}-volume`).oninput = event => change(device, event.target.value);
    el(`${device}-down`).onclick = () => change(device, Number(el(`${device}-volume`).value) - 5, true);
    el(`${device}-up`).onclick = () => change(device, Number(el(`${device}-volume`).value) + 5, true);
  }
  panel.addEventListener('toggle', () => { if (panel.open) void load(); });
})();
