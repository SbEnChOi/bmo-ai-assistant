'use strict';
const $ = id => document.getElementById(id);
let state = null, token = '', pending = false, eventSignature = '', imageVersion = -1, previewUrl = null;
let cameraPending = false, cameraPreviewUrl = null;

function error(message = '') { $('error').textContent = message; }
async function api(path, body = {}) {
  const raw = body instanceof Blob;
  const response = await fetch('/api/' + path, {method:'POST', headers:{'Content-Type':raw ? body.type : 'application/json','X-BMO-Token':token}, body:raw ? body : JSON.stringify(body)});
  const result = await response.json();
  if (result.pair_required) $('pair-panel').hidden = false;
  if (!response.ok) throw Error(result.error || '요청을 처리하지 못했어요.');
  return result;
}
function renderEvents(events) {
  const signature = JSON.stringify(events);
  if (signature === eventSignature) return;
  eventSignature = signature;
  $('events').replaceChildren();
  if (!events.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = '아직 나눈 대화가 없습니다.'; $('events').append(p); return; }
  for (const item of events) {
    const row = document.createElement('div'); row.className = 'message'; row.dataset.role = item.role;
    const label = document.createElement('strong'); label.textContent = item.role === 'assistant' ? 'BMO' + (item.emotion ? ' · ' + item.emotion : '') : item.origin === 'phone' ? '아이폰' : 'PC';
    const content = document.createElement('span'); content.textContent = item.text;
    row.append(label, content); $('events').append(row);
  }
  $('events').scrollTop = $('events').scrollHeight;
}
async function renderImage(s) {
  if (imageVersion === s.image_version) return;
  imageVersion = s.image_version;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  $('image-preview').hidden = !s.image_name;
  if (!s.image_name) { $('preview').removeAttribute('src'); return; }
  $('image-name').textContent = s.image_name;
  try {
    const response = await fetch('/api/admin/image');
    if (!response.ok) throw Error();
    previewUrl = URL.createObjectURL(await response.blob());
    $('preview').src = previewUrl;
  } catch { error('사진 미리보기를 불러오지 못했어요.'); }
}
function update(s) {
  state = s; token = s.token; $('pair-panel').hidden = true;
  $('connection').textContent = '● 서버 연결됨'; $('connection').classList.remove('offline');
  $('phone-online').textContent = s.phone_online ? '● 아이폰 연결됨' : '○ 아이폰 대기 중'; $('phone-online').classList.toggle('offline', !s.phone_online);
  $('provider').textContent = s.provider === 'mock' ? '모의 모드' : s.provider === 'claude' ? 'Claude' : 'OpenAI';
  $('source').textContent = ['pi','ssh-pi'].includes(s.source) ? 'Pi 카메라' : s.source === 'image' ? '시작 사진' : '연결 안 됨';
  $('camera-preview-button').disabled = !s.camera_available || s.busy || cameraPending;
  $('calls').textContent = s.calls + '회';
  $('phase').textContent = s.busy ? ({transcribing:'음성 인식 중',capturing:'촬영 중',thinking:'답변 준비 중',synthesizing:'음성 생성 중'}[s.phase] || '처리 중') : '대기 중';
  $('queue-status').textContent = s.queued ? `대기 중인 요청 ${s.queued}개 · 순서대로 처리합니다.` : '두 화면의 요청은 순서대로 처리됩니다.';
  $('send').disabled = pending || !!s.realtime?.active;
  $('reset').disabled = !!s.realtime?.active;
  $('admin-rt-stop').disabled = !s.realtime?.active;
  $('admin-rt-status').textContent = s.realtime?.active ? `${s.realtime.mock ? '모의' : s.realtime.model} · ${s.realtime.seconds}초 · ${s.realtime.phase}` : s.realtime?.warning || '꺼짐';
  window.BmoFrames?.update(s);
  window.BmoObservation?.update(s.observation);
  $('upload').disabled = !$('image-file').files.length;
  for (const radio of document.querySelectorAll('input[name="scene"]')) {
    radio.checked = radio.value === s.scene_mode;
    radio.disabled = (radio.value === 'camera' && !s.camera_available) || (radio.value === 'upload' && !s.image_name) || (radio.value === 'frames' && !s.frames?.selected);
  }
  $('scene-note').textContent = s.scene_mode === 'frames' ? '다음 질문에 시간 순서가 있는 프레임을 최대 4장 첨부합니다.' : s.scene_mode === 'upload' ? '다음 질문에는 PC에서 올린 사진 한 장을 첨부합니다.' : s.scene_mode === 'camera' ? '다음 질문이 들어오면 카메라로 사진 한 장을 촬영합니다.' : s.observation?.enabled ? '질문에 자동 관찰의 최신 프레임과 최근 기억을 첨부합니다.' : '지금은 사진을 질문에 첨부하지 않습니다.';
  renderEvents(s.events);
  void renderImage(s);
}
async function refresh() {
  try {
    const response = await fetch('/api/state?role=pc');
    const data = await response.json();
    if (response.status === 401) { $('pair-panel').hidden = false; return; }
    if (!response.ok) throw Error(data.error || '서버에 연결하지 못했어요.');
    update(data);
  } catch {
    $('connection').textContent = '○ 연결 끊김'; $('connection').classList.add('offline');
    $('send').disabled = true;
  }
}
async function poll() { await refresh(); setTimeout(poll, 1000); }

$('chat').onsubmit = async event => {
  event.preventDefault(); if (pending || !state) return;
  const question = $('question').value.trim(); if (!question) return;
  pending = true; $('send').disabled = true; error(''); $('question').value = '';
  try { await api('chat', {question, camera:state.scene_mode !== 'off'}); }
  catch (exc) { error(exc.message); $('question').value = question; }
  finally { pending = false; await refresh(); }
};
$('pair-form').onsubmit = async event => {
  event.preventDefault();
  try { await api('pair', {code:$('pair-code').value.trim()}); $('pair-code').value = ''; error(''); await refresh(); }
  catch (exc) { error(exc.message); }
};
$('image-file').onchange = () => { $('upload').disabled = !$('image-file').files.length; };
$('upload').onclick = async () => {
  const file = $('image-file').files[0]; if (!file) return;
  if (!['image/jpeg','image/png'].includes(file.type) || file.size > 20 * 1024 * 1024) { error('20 MB 이하의 JPG 또는 PNG 사진을 선택하세요.'); return; }
  $('upload').disabled = true; error('');
  try { await api('admin/image', file); $('image-file').value = ''; await refresh(); }
  catch (exc) { error(exc.message); $('upload').disabled = false; }
};
$('clear-image').onclick = async () => { try { await api('admin/image/clear'); error(''); await refresh(); } catch (exc) { error(exc.message); } };
for (const radio of document.querySelectorAll('input[name="scene"]')) {
  radio.onchange = async () => { if (!radio.checked) return; try { await api('admin/scene', {mode:radio.value}); error(''); await refresh(); } catch (exc) { error(exc.message); await refresh(); } };
}
$('reset').onclick = async () => { try { await api('reset'); error(''); await refresh(); } catch (exc) { error(exc.message); } };
$('camera-preview-button').onclick = async () => {
  if (cameraPending || !state?.camera_available) return;
  cameraPending = true; $('camera-preview-button').disabled = true; error('');
  try {
    const response = await fetch('/api/admin/capture', {method:'POST',headers:{'Content-Type':'application/json','X-BMO-Token':token},body:'{}'});
    if (!response.ok) { const data = await response.json(); if (data.pair_required) $('pair-panel').hidden = false; throw Error(data.error || '카메라 사진을 받지 못했어요.'); }
    const blob = await response.blob();
    if (cameraPreviewUrl) URL.revokeObjectURL(cameraPreviewUrl);
    cameraPreviewUrl = URL.createObjectURL(blob);
    $('camera-live').src = cameraPreviewUrl; $('camera-preview').hidden = false;
  } catch (exc) { error(exc.message); }
  finally { cameraPending = false; await refresh(); }
};
window.addEventListener('pagehide', () => { if (previewUrl) URL.revokeObjectURL(previewUrl); if (cameraPreviewUrl) URL.revokeObjectURL(cameraPreviewUrl); });
poll();
window.BmoAdmin = {api, state:()=>state, refresh};
$('admin-rt-stop').onclick = async()=>{ try { await api('admin/realtime/stop'); await refresh(); } catch(exc) { error(exc.message); } };
