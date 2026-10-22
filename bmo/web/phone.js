'use strict';
const $ = id => document.getElementById(id);
const labels = {idle:'안녕! 오늘은 어떤 이야기를 해볼까?',permission:'마이크 사용을 허용해 줘.',listening:'듣고 있어!',transcribing:'네 말을 듣고 있어.',capturing:'장면을 보고 있어.',thinking:'생각하고 있어…',synthesizing:'목소리를 준비하고 있어.',speaking:'내가 이야기할게!',cancelling:'잠시만 기다려 줘.',muted:'잠시 쉬는 중 · 마이크 꺼짐',connecting:'자동 대화 연결 중',closing:'자동 대화를 종료하고 있어.'};
let state = null, token = '', local = 'idle', connected = false, recording = null, controller = null, requestId = 0, seenReplyId = null, replyQueue = [], loadingReply = false, audioUrl = null, wakeLock = null;
let primingAudio = false, primingUrl = null;
let replyEmotion = null;
let proactiveReply = null, activityPhase = '', activityAt = -Infinity;
const player = $('player');

function error(message = '') { $('error').textContent = message; }
function presentPhase(phase, caption = labels[phase] || phase) {
  const waiting = ['transcribing','capturing','thinking','synthesizing'].includes(phase);
  const faceState = ['permission','transcribing','capturing','synthesizing','cancelling'].includes(phase) ? 'thinking' : phase === 'muted' ? 'idle' : phase;
  $('face').dataset.state = faceState;
  window.BmoFace?.setMode(faceState);
  $('face').setAttribute('aria-label', caption);
  $('face').setAttribute('aria-busy', String(waiting));
  $('response-pending').hidden = !waiting;
  $('status').textContent = caption;
  $('status').hidden = phase === 'idle' || waiting;
}
function display(phase) {
  presentPhase(phase);
  const isRecording = phase === 'listening';
  $('talk').classList.toggle('recording', isRecording);
  $('talk-label').textContent = isRecording ? '다시 눌러 보내기' : '눌러서 말하기';
  $('talk').disabled = !!state?.realtime?.active || !!window.BmoRealtime?.active() || !connected || !state?.voice_ready || (!isRecording && local !== 'idle') || !window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder;
  $('enable-sound').disabled = !!state?.realtime?.active || !!window.BmoRealtime?.active() || !connected || !state?.voice_ready || local !== 'idle' || loadingReply || primingAudio;
  $('hint').textContent = isRecording ? '최대 45초 · ×를 누르면 녹음을 취소해.' : state?.provider === 'mock' ? '모의 모드에서는 음성을 인식하지 못해.' : '한 번 눌러 녹음하고, 다시 눌러 보내 줘.';
  void reportActivity();
}
async function reportActivity() {
  if (!connected || !state?.observation?.enabled) return;
  const phase = document.hidden ? 'hidden' : window.BmoRealtime?.active() ? 'listening' : local;
  if (phase === activityPhase && performance.now() - activityAt < 2400) return;
  activityPhase = phase; activityAt = performance.now();
  try { await api('phone/activity', {phase}); } catch { activityPhase = ''; }
}
function validProactive(reply) {
  return reply.kind !== 'proactive' || (!!state?.observation?.enabled && !!state?.observation?.proactive
    && reply.observation_generation === state.observation.generation && Date.now() < reply.expires_at * 1000);
}
async function api(path, body = {}, headers = {}, signal) {
  const raw = body instanceof Blob;
  const deadline = !signal && /^(realtime|live)\//.test(path) ? new AbortController() : null;
  const timer = deadline ? setTimeout(()=>deadline.abort(), /^(realtime|live)\/(start|stop)$/.test(path)?55000:10000) : null;
  try {
    const response = await fetch('/api/' + path, {method:'POST', headers:{'Content-Type':raw ? body.type : 'application/json','X-BMO-Token':token,...headers},body:raw ? body : JSON.stringify(body),signal:signal || deadline?.signal,keepalive:/^(realtime|live)\/stop$/.test(path)});
    const data = await response.json();
    if (data.pair_required) { connected = false; $('pair-panel').hidden = false; }
    if (!response.ok) throw Error(data.error || '요청을 처리하지 못했어.');
    return data;
  } finally { if (timer) clearTimeout(timer); }
}
function releaseAudio() {
  player.pause(); player.removeAttribute('src'); player.load();
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  if (primingUrl) URL.revokeObjectURL(primingUrl);
  audioUrl = null;
  replyEmotion = null;
  proactiveReply = null;
  primingUrl = null; primingAudio = false;
  $('replay').hidden = true;
}
function idle() { local = 'idle'; display(state?.busy ? state.phase : 'idle'); }
async function playReply() {
  if (!audioUrl) return;
  if (replyEmotion) window.BmoFace?.setEmotion?.(replyEmotion.label, replyEmotion.key);
  try { await player.play(); $('enable-sound').hidden = true; error(''); }
  catch { $('enable-sound').hidden = false; error('BMO 소리 켜기 또는 ↻를 눌러 목소리를 들어 줘.'); idle(); }
}
async function enableSound() {
  if (!connected || !state?.voice_ready || local !== 'idle' || loadingReply || primingAudio) return;
  window.BmoFace?.unlockAudio();
  if (audioUrl) return playReply();
  // Start this same media element directly in the tap handler. A short quiet
  // tone confirms the output without asking for microphone access or an API call.
  releaseAudio();
  const samples = 800, bytes = new Uint8Array(44 + samples * 2), view = new DataView(bytes.buffer);
  const ascii = (offset, value) => [...value].forEach((char, i) => { bytes[offset + i] = char.charCodeAt(0); });
  ascii(0, 'RIFF'); view.setUint32(4, bytes.length - 8, true); ascii(8, 'WAVE'); ascii(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 8000, true); view.setUint32(28, 16000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  ascii(36, 'data'); view.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i++) view.setInt16(44 + i * 2, Math.sin(2 * Math.PI * 440 * i / 8000) * Math.sin(Math.PI * i / samples) * 1200, true);
  primingAudio = true; primingUrl = URL.createObjectURL(new Blob([bytes], {type:'audio/wav'})); player.src = primingUrl; display(local);
  try { await player.play(); $('enable-sound').hidden = true; error(''); }
  catch { releaseAudio(); error('소리를 켜지 못했어. 기기 음량을 확인하고 다시 눌러 줘.'); idle(); void playNextReply(); }
}
async function playNextReply() {
  if (window.BmoRealtime?.active() || state?.realtime?.active) return;
  if (loadingReply || primingAudio || local !== 'idle' || !replyQueue.length) return;
  const next = replyQueue.shift();
  if (!validProactive(next)) { void playNextReply(); return; }
  releaseAudio();
  $('transcript').textContent = next.text;
  if (!next.audio_ready) { void playNextReply(); return; }
  loadingReply = true;
  const generation = requestId;
  let failed = false;
  try {
    const response = await fetch('/api/audio/' + next.id);
    if (!response.ok) throw Error();
    const blob = await response.blob();
    if (local !== 'idle') { replyQueue.unshift(next); return; }
    if (generation !== requestId) return;
    if (!validProactive(next)) return;
    audioUrl = URL.createObjectURL(blob);
    proactiveReply = next.kind === 'proactive' ? next : null;
    replyEmotion = {label:next.emotion || '평온', key:'reply:' + next.id};
    player.src = audioUrl;
    $('replay').hidden = false;
    if (!next.previewOnly) await playReply();
  } catch { failed = true; error('답변 음성을 가져오지 못했어. PC 화면의 글을 확인해 줘.'); idle(); }
  finally { loadingReply = false; display(local); if (failed) void playNextReply(); }
}
function queueReplies(s) {
  if (seenReplyId === null) {
    seenReplyId = s.reply_id;
    const latest = (s.replies || []).find(reply => reply.id === s.reply_id);
    if (latest) { replyQueue.push({...latest, previewOnly:true}); void playNextReply(); }
    return;
  }
  if (s.reply_id > seenReplyId && !(s.replies || []).length) {
    seenReplyId = s.reply_id; replyQueue = []; releaseAudio(); $('transcript').textContent = '';
    if (local === 'speaking' || local === 'idle') idle();
    return;
  }
  for (const reply of s.replies || []) {
    if (reply.id > seenReplyId && !(reply.kind === 'proactive' && (local !== 'idle' || controller || recording))) replyQueue.push(reply);
  }
  seenReplyId = Math.max(seenReplyId, s.reply_id);
  void playNextReply();
}
function update(s) {
  state = s; token = s.token; connected = true; $('pair-panel').hidden = true;
  $('connection').textContent = '● 연결됨'; $('connection').classList.remove('offline');
  $('scene-pill').textContent = s.scene_mode === 'frames' ? `PC 프레임 ${s.frames?.selected || 0}장 준비됨` : s.scene_mode === 'upload' ? 'PC 사진 준비됨' : s.scene_mode === 'camera' ? '질문할 때 카메라 촬영' : '장면 입력 꺼짐';
  if (s.observation?.enabled) $('scene-pill').textContent = s.observation.fresh ? `관찰 중 · ${s.observation.proactive ? '먼저 말하기 켜짐' : '기억만 하기'}` : '카메라 확인 중';
  $('scene-pill').hidden = s.scene_mode === 'off' && !s.observation?.enabled;
  window.BmoObservation?.update(s.observation);
  if (proactiveReply && !validProactive(proactiveReply)) { releaseAudio(); idle(); }
  if (!window.BmoRealtime?.active()) {
    if (local === 'idle') display(s.realtime?.active ? s.realtime.phase : s.busy ? s.phase : 'idle');
    else display(controller && s.busy ? s.phase : local);
  }
  window.BmoRealtime?.update(s);
  if (s.voice_ready && !window.isSecureContext) error('아이폰 마이크는 신뢰된 HTTPS 주소에서 사용할 수 있어.');
  else if (s.voice_ready && (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia)) error('이 브라우저에서는 녹음을 사용할 수 없어. Safari에서 열어 줘.');
  queueReplies(s);
  void reportActivity();
}
async function refresh() {
  try {
    const response = await fetch('/api/state?role=phone'); const data = await response.json();
    if (response.status === 401) { connected = false; $('pair-panel').hidden = false; display('idle'); return; }
    if (!response.ok) throw Error();
    update(data);
  } catch { connected = false; $('connection').textContent = '○ 연결 끊김'; $('connection').classList.add('offline'); display(local); }
}
async function poll() { await refresh(); setTimeout(poll, 800); }
function finishRecording(cancel = false) {
  const r = recording; if (!r) return;
  r.cancelled = r.cancelled || cancel; clearInterval(r.timer);
  if (r.recorder.state !== 'inactive') r.recorder.stop();
  r.stream.getTracks().forEach(track => track.stop());
}
async function submitVoice(blob) {
  const id = ++requestId; releaseAudio(); error(''); local = 'transcribing'; display(local);
  controller = new AbortController(); const current = controller;
  const timeout = setTimeout(() => current.abort(), 240000);
  try {
    const result = await api('voice', blob, {'X-BMO-Camera':state?.scene_mode !== 'off' ? '1' : '0'}, current.signal);
    if (id !== requestId || result.cancelled) return;
    $('transcript').textContent = result.question ? `내 말: ${result.question}` : '';
    if (result.warning) error(result.warning);
    await refresh();
  } catch (exc) {
    if (id === requestId) { error(exc.name === 'AbortError' ? '응답이 오래 걸려 중단했어. 다시 시도해 줘.' : exc.message); if (exc.name === 'AbortError') void api('cancel').catch(()=>{}); idle(); }
  } finally { clearTimeout(timeout); if (id === requestId) { controller = null; if (local !== 'speaking') idle(); void refresh(); void playNextReply(); } }
}
async function startRecording() {
  if (state?.realtime?.active || window.BmoRealtime?.active()) return;
  if (recording) { finishRecording(); return; }
  if (!connected || !state?.voice_ready || local !== 'idle') return;
  window.BmoFace?.unlockAudio();
  releaseAudio(); error(''); const id = ++requestId; local = 'permission'; display(local);
  replyQueue = replyQueue.filter(reply => reply.kind !== 'proactive');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
    if (id !== requestId || document.hidden) { stream.getTracks().forEach(track => track.stop()); return; }
    let recorder;
    try { const mime = ['audio/mp4','audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type)); recorder = mime ? new MediaRecorder(stream,{mimeType:mime}) : new MediaRecorder(stream); }
    catch (exc) { stream.getTracks().forEach(track => track.stop()); throw exc; }
    const r = {recorder,stream,chunks:[],size:0,started:performance.now(),cancelled:false,timer:null,id}; recording = r;
    recorder.ondataavailable = event => { if (event.data.size) { r.chunks.push(event.data); r.size += event.data.size; if (r.size > 8 * 1024 * 1024) { error('녹음이 너무 커서 취소했어.'); finishRecording(true); } } };
    recorder.onerror = () => { error('녹음 중 오류가 났어. 마이크를 확인해 줘.'); finishRecording(true); };
    recorder.onstop = () => { clearInterval(r.timer); stream.getTracks().forEach(track => track.stop()); if (recording === r) recording = null; if (r.cancelled || id !== requestId) { if (id === requestId) idle(); return; } const blob = new Blob(r.chunks,{type:recorder.mimeType || r.chunks[0]?.type || 'audio/mp4'}); if (performance.now()-r.started < 400 || blob.size < 100) { error('녹음이 너무 짧아. 다시 말해 줘.'); idle(); return; } void submitVoice(blob); };
    recorder.start(250); local = 'listening'; display(local);
    r.timer = setInterval(() => { const seconds = Math.floor((performance.now()-r.started)/1000); $('status').textContent = `듣고 있어! · ${seconds} / 45초`; if (seconds >= 45) finishRecording(); }, 250);
    try { if ('wakeLock' in navigator && !wakeLock) wakeLock = await navigator.wakeLock.request('screen'); } catch {}
  } catch (exc) { if (id === requestId) { finishRecording(true); recording = null; error(exc.name === 'NotAllowedError' ? '마이크 사용을 허용해 줘.' : `마이크를 시작하지 못했어. ${exc.message}`); idle(); } }
}
async function cancel() {
  if (window.BmoRealtime?.active()) { window.BmoRealtime.interrupt(); return; }
  ++requestId; finishRecording(true); controller?.abort(); controller = null; replyQueue = []; releaseAudio(); idle();
  if (connected) { try { await api('cancel'); } catch (exc) { error(exc.message); } }
  await refresh();
}
player.onplaying = () => { if (!primingAudio) { local = 'speaking'; display(local); } };
player.onended = () => { if (primingAudio) releaseAudio(); idle(); void playNextReply(); };
player.onerror = () => { const wasPriming = primingAudio; if (wasPriming) releaseAudio(); $('enable-sound').hidden = false; error('목소리를 재생하지 못했어. 소리 켜기 또는 다시 듣기를 눌러 줘.'); idle(); if (wasPriming) void playNextReply(); };
$('talk').onclick = startRecording; $('cancel').onclick = cancel; $('replay').onclick = () => { window.BmoFace?.unlockAudio(); return playReply(); };
$('enable-sound').onclick = enableSound;
$('pair-form').onsubmit = async event => { event.preventDefault(); try { await api('pair',{code:$('pair-code').value.trim()}); $('pair-code').value = ''; error(''); await refresh(); } catch (exc) { error(exc.message); } };
document.addEventListener('visibilitychange', () => { if (document.hidden && (recording || local === 'permission' || controller)) void cancel(); void reportActivity(); });
window.addEventListener('pagehide', () => { ++requestId; finishRecording(true); controller?.abort(); releaseAudio(); window.BmoFace?.stop(); });
poll();
window.BmoPhone = {api, state: () => state, busy: () => local !== 'idle' || !!recording || !!controller || loadingReply,
  observationChanged: data => { if (state) update({...state, observation:data}); },
  presentPhase,
  prepareRealtime: () => { ++requestId; replyQueue = []; releaseAudio(); },
  restore: () => { idle(); void refresh(); void playNextReply(); }};
