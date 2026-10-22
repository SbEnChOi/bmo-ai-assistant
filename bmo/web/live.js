'use strict';
(() => {
  if (document.querySelector?.('meta[name="bmo-dialogue-mode"]')?.content !== 'live') return;
  const el = id => document.getElementById(id), phone = window.BmoPhone, audio = el('rt-player');
  let current = null, shared = null, serial = 0;
  el('rt-description').textContent = 'GPT-Live-1 · 노을(noeul). 음성은 OpenAI로 전송돼요. 세션 $0.05/분(침묵·분석 대기도 포함), 분석 비용 별도 · 최대 5분. 눌러서 말하기와 대기 안내는 기존 coral 음성이에요.';
  el('rt-vision-label').textContent = '질문할 때 준비한 사진도 분석';
  function status(text) { el('rt-status').textContent = text; }
  function controls() {
    const c = current;
    el('rt-start').textContent = c?.closing ? '노을 대화 종료 중…' : c ? '노을 대화 종료' : '노을과 대화 시작';
    el('rt-start').disabled = !!c?.closing || (!c && (!shared || shared.realtime?.active || phone.busy() || shared.provider !== 'openai' || !window.isSecureContext || !window.RTCPeerConnection || !navigator.mediaDevices?.getUserMedia));
    el('rt-start').setAttribute('aria-pressed', String(!!c));
    el('rt-mock').disabled = !!c || !shared || !!shared.realtime?.active || phone.busy();
    for (const id of ['rt-stop','rt-mute','rt-interrupt']) { el(id).hidden = !c; el(id).disabled = !c?.ready || !!c?.closing; }
    el('rt-mute').disabled ||= !!c?.mock;
    el('rt-sample').hidden = !c?.mock || !c?.id;
    el('talk').disabled = !!c || !!shared?.realtime?.active || el('talk').disabled;
    el('talk').title = c || shared?.realtime?.active ? '노을 대화를 종료하면 눌러서 말할 수 있어요.' : '';
  }
  function phase(c) {
    if (current !== c || c.closing) return;
    const next = c.playing ? 'speaking' : c.pending ? 'thinking' : c.muted ? 'muted' : 'listening';
    c.phase = next;
    phone.presentPhase(next, {speaking:'노을이 이야기 중 · 함께 말해도 괜찮아',thinking:'사진과 질문을 생각하고 있어…',muted:'마이크 꺼짐',listening:'노을이 듣고 있어!'}[next]);
  }
  function send(c, type, extra={}) {
    if (current !== c || !c.ready || c.dc?.readyState !== 'open') return false;
    try { c.dc.send(JSON.stringify({type, event_id:'bmo_ui_' + (++serial), ...extra})); return true; }
    catch { return false; }
  }
  function metrics(c) {
    el('rt-metrics').textContent = c.mock ? '모의 연결 · 실제 음성·이미지 분석·과금 없음' :
      `연결 ${c.connectMs ?? '—'}ms · 서버 사용량 ${c.seconds ?? 0}초 · 음성 약 $${((c.seconds || 0) / 60 * .05).toFixed(3)} (분석 별도${c.finalized ? ' · 종료 확인' : ' · 최종 사용량 미확정'})`;
  }
  async function playAudio() {
    try { await audio.play(); el('rt-audio').hidden = true; }
    catch { el('rt-audio').hidden = false; status('실시간 소리 켜기를 눌러주세요.'); }
  }
  async function emotion(c, segment) {
    if (segment.requested || !c.id || segment.text.trim().length < 8) return;
    if (segment.text.length < 80 && !/[.!?。！？\n]/.test(segment.text)) return;
    segment.requested = true;
    try {
      const result = await phone.api('live/emotion', {session_id:c.id,response_id:segment.id,text:segment.text.slice(0,600)});
      if (current !== c || c.closing || c.parts.assistant !== segment || result.cancelled) return;
      segment.emotion = result.emotion || '평온';
      if (c.playing) window.BmoFace?.setEmotion?.(segment.emotion, segment.id);
    } catch { /* Facial metadata never holds audio. */ }
  }
  function transcript(c, ev, role) {
    if (typeof ev.delta !== 'string' || !ev.delta || ev.delta.length > 8000) return;
    if (ev.event_id && c.seen.has(ev.event_id)) return;
    if (c.seen.size >= 5000) { void stop('자막 한도에 도달해 대화를 종료합니다.'); return; }
    if (ev.event_id) c.seen.add(ev.event_id);
    let part = c.parts[role];
    if (!part || (typeof ev.start_ms === 'number' && typeof part.end === 'number' && ev.start_ms - part.end > 1800) || part.text.length + ev.delta.length > 4000) {
      part = c.parts[role] = {id:'live_' + (++serial),text:'',end:null};
      if (role === 'assistant') window.BmoFace?.beginUtterance?.(part.id);
    }
    part.text += ev.delta; part.end = ev.end_ms;
    el(role === 'user' ? 'live-input' : 'live-output').textContent = (role === 'user' ? '내 말: ' : 'BMO: ') + part.text.slice(-220);
    if (role === 'assistant') { c.pending = false; void emotion(c, part); }
    phase(c);
  }
  function event(c, ev) {
    if (current !== c) return;
    switch (ev.type) {
      case 'session.started':
        c.ready = true; c.connectMs = Math.round(performance.now() - c.started);
        clearTimeout(c.connectLimit); status('노을 연결됨 · 최대 5분'); controls(); metrics(c); phase(c); break;
      case 'session.input_transcript.delta': transcript(c, ev, 'user'); break;
      case 'session.output_transcript.delta': transcript(c, ev, 'assistant'); break;
      case 'session.delegation.created': c.pending = true; phase(c); break;
      case 'session.commentary.appended': c.pending = false; phase(c); break;
      case 'session.input_audio.muted': status('노을 연결됨 · 마이크 꺼짐 확인'); break;
      case 'session.input_audio.unmuted': status('노을 연결됨 · 마이크 켜짐 확인'); break;
      case 'session.usage.updated':
        if (Number.isFinite(ev.usage?.seconds)) c.seconds = ev.usage.seconds;
        metrics(c); break;
      case 'session.closed':
        c.finalized = true;
        if (Number.isFinite(ev.usage?.seconds)) c.seconds = ev.usage.seconds;
        metrics(c); c.closedEvent?.(); if (!c.closing) void stop('노을 대화가 종료됐습니다.'); break;
      case 'error': status('Live 요청 오류 · API 권한과 연결을 확인하세요.'); break;
    }
  }
  function meter(c, stream) {
    try {
      const ctx = c.context; if (!ctx) return;
      const source = ctx.createMediaStreamSource(stream), analyser = ctx.createAnalyser();
      analyser.fftSize = 256; source.connect(analyser);
      const samples = new Uint8Array(256);
      c.meter = setInterval(() => {
        if (current !== c || c.closing || ctx.state !== 'running') return;
        analyser.getByteTimeDomainData(samples);
        const level = Math.sqrt(samples.reduce((n,v)=>n+((v-128)/128)**2,0)/samples.length);
        if (level > .015) {c.lastSound=performance.now();c.activityAt=performance.now();}
        const playing = performance.now() - (c.lastSound ?? -Infinity) < 300;
        if (c.silencing && (!playing || performance.now() - c.silencing > 8000)) { c.silencing = 0; audio.muted = false; }
        const audible = playing && !audio.muted && !audio.paused;
        if (audible !== c.playing) {
          c.playing = audible;
          const part = c.parts.assistant;
          if (audible && part?.emotion) window.BmoFace?.setEmotion?.(part.emotion, part.id);
          phase(c);
        }
      },100);
    } catch { status('음성 연결됨 · 이 브라우저에서는 말하기 표정 측정이 제한돼요.'); }
  }
  function ice(c) {
    if (c.pc.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise((resolve,reject) => {
      const timer = setTimeout(()=>{cleanup();reject(Error('네트워크 연결 준비 시간이 초과됐어요.'));},10000);
      const changed = ()=>{if(c.pc.iceGatheringState==='complete'){cleanup();resolve();}};
      function cleanup(){clearTimeout(timer);c.pc.removeEventListener('icegatheringstatechange',changed);c.cancelIce=null;}
      c.cancelIce=()=>{cleanup();reject(Error('연결이 취소됐어요.'));};
      c.pc.addEventListener('icegatheringstatechange',changed); changed();
    });
  }
  async function heartbeat(c) {
    if (current !== c || !c.id || c.closing || c.syncing) return;
    c.syncing = true;
    try {
      await phone.api('live/heartbeat',{session_id:c.id,phase:c.phase || 'listening',manual:el('rt-vision').checked,
        input_active:!!c.inputActive,quiet_ms:Math.min(300000,Math.max(0,performance.now()-c.activityAt))});
    } catch { if (current === c && !c.closing) await stop('서버 연결을 잃어 노을 대화를 종료합니다.'); }
    finally { c.syncing=false; }
  }
  async function start(mock=false) {
    if (current || !shared || phone.busy() || shared.realtime?.active) return;
    const c = {mock,id:null,ready:false,parts:{},seen:new Set(),started:performance.now(),activityAt:performance.now(),phase:'listening'};
    current=c; phone.prepareRealtime(); el('error').textContent='';
    el('transcript').hidden=true;
    for (const id of ['live-input','live-output']) { el(id).hidden=false; el(id).textContent=''; }
    controls(); metrics(c); status(mock?'노을 모의 연결 중…':'마이크와 노을 연결 준비 중…');
    el('rt-mute').textContent='마이크 끄기';
    if (!mock) {
      window.BmoFace?.unlockRealtimeAudio?.(audio);
      const Context = window.AudioContext || window.webkitAudioContext;
      try { if (Context) { c.context=new Context(); void c.context.resume().catch(()=>{}); } } catch {}
      audio.muted=false; void audio.play().catch(()=>{});
    }
    try {
      let sdp='';
      if (!mock) {
        const stream=await navigator.mediaDevices.getUserMedia({audio:window.BmoMicFocus?.constraints()||{echoCancellation:true,noiseSuppression:true,autoGainControl:false},video:false});
        if (current!==c || c.closing) { stream.getTracks().forEach(t=>t.stop()); return; }
        c.stream=stream;
        c.focusAbort=new AbortController();
        c.focus=await window.BmoMicFocus?.attach(stream,state=>{if(current===c&&!c.closing){
          if(state.failed){void stop('입력 필터 오류로 대화를 종료했어요. 다시 시작해 주세요.');return;}
          c.inputActive=!!state.active&&!c.muted;if(c.inputActive)c.activityAt=performance.now();}},c.focusAbort.signal);
        if(current!==c||c.closing){stream.getTracks().forEach(t=>t.stop());void c.focus?.close();return;}
        c.pc=new RTCPeerConnection();const sendStream=c.focus?.stream||stream;sendStream.getTracks().forEach(t=>c.pc.addTrack(t,sendStream));
        c.pc.ontrack=ev=>{if(current===c&&!c.closing){const remote=ev.streams[0] || new MediaStream([ev.track]);audio.srcObject=remote;meter(c,remote);void playAudio();}};
        c.pc.onconnectionstatechange=()=>{
          if(current!==c||c.closing)return;
          if(['failed','closed'].includes(c.pc.connectionState))void stop('노을 연결이 끊겼습니다.');
          if(c.pc.connectionState==='disconnected'&&!c.disconnectTimer)c.disconnectTimer=setTimeout(()=>{c.disconnectTimer=null;if(current===c&&c.pc.connectionState==='disconnected')void stop('노을 연결이 끊겼습니다.');},8000);
        };
        c.dc=c.pc.createDataChannel('oai-events');
        c.dc.onmessage=msg=>{try{event(c,JSON.parse(msg.data));}catch{}};
        c.dc.onclose=()=>{if(current===c&&!c.closing)void stop('노을 통신이 종료됐습니다.');};
        await c.pc.setLocalDescription(await c.pc.createOffer()); await ice(c);
        if(current!==c||c.closing)return;
        sdp=c.pc.localDescription.sdp;
      }
      const result=await phone.api('live/start',{sdp,mock});
      if(current!==c||c.closing){await phone.api('live/stop',{session_id:result.session_id}).catch(()=>{});return;}
      c.id=result.session_id;
      if(mock){c.ready=true;status('노을 모의 연결 · 실제 음성·분석은 하지 않아요');}
      else {
        c.connectLimit=setTimeout(()=>{if(current===c&&!c.ready)void stop('노을 연결 시간이 초과됐습니다.');},20000);
        await c.pc.setRemoteDescription({type:'answer',sdp:result.sdp});
      }
      if(current!==c||c.closing)return;
      c.timer=setInterval(()=>void heartbeat(c),2000);
      c.limit=setTimeout(()=>void stop('5분 세션이 끝났습니다. 필요하면 다시 시작하세요.'),300000);
      controls(); phase(c); void heartbeat(c);
    } catch(error){if(current===c&&!c.closing)await stop('연결 실패: '+error.message);}
  }
  async function stop(message='노을 대화 꺼짐') {
    const c=current;if(!c||c.closing)return;
    c.closing=true;controls();
    for(const id of ['timer','meter'])clearInterval(c[id]);
    for(const id of ['connectLimit','limit','disconnectTimer','unmuteTimer'])clearTimeout(c[id]);
    c.cancelIce?.();c.stream?.getTracks().forEach(t=>t.stop());audio.pause();audio.muted=true;
    c.focusAbort?.abort();
    c.focus?.stream?.getTracks().forEach(t=>t.stop());void c.focus?.close();
    // Keep the data channel alive until server finalization, while audio is already stopped.
    send(c,'session.close');
    if(c.id){
      try{const result=await phone.api('live/stop',{session_id:c.id});if(result.warning)message=result.warning;}
      catch{if(!c.finalized)message+=' · 서버 종료 확인 실패, 서버가 재시도합니다.';}
    }
    c.dc?.close();c.pc?.close();audio.srcObject=null;void c.context?.close().catch(()=>{});
    el('rt-audio').hidden=true;el('transcript').hidden=false;
    current=null;status(message);controls();phone.restore();
  }
  function interrupt() {
    const c=current;if(!c||!c.ready||c.closing)return;
    if(!c.mock){
      audio.muted=true;c.silencing=performance.now();
      send(c,'session.instructions.append',{delegation_id:null,content:'지금 하던 말을 멈추고 사용자의 다음 말을 들어 주세요.'});
      clearTimeout(c.unmuteTimer);c.unmuteTimer=setTimeout(()=>{if(current===c&&!c.closing){audio.muted=false;c.silencing=0;}},8000);
    }
    c.playing=false;c.pending=false;phase(c);
  }
  el('rt-start').onclick=()=>current?stop():start();el('rt-stop').onclick=()=>stop();el('rt-mock').onclick=()=>start(true);
  el('rt-audio').onclick=playAudio;el('rt-interrupt').onclick=interrupt;
  el('rt-mute').onclick=()=>{
    const c=current;if(!c?.ready||!c.stream||c.closing)return;
    c.muted=!c.muted;c.stream.getAudioTracks().forEach(t=>t.enabled=!c.muted);
    c.focus?.stream?.getAudioTracks().forEach(t=>t.enabled=!c.muted);c.activityAt=performance.now();
    send(c,c.muted?'session.input_audio.mute':'session.input_audio.unmute');
    el('rt-mute').textContent=c.muted?'마이크 켜기':'마이크 끄기';status('마이크 변경 확인 중…');phase(c);
  };
  el('rt-vision').onchange=()=>{if(current)void heartbeat(current);};
  el('rt-sample').onclick=()=>{
    const c=current;if(!c?.mock)return;
    event(c,{type:'session.input_transcript.delta',delta:'[모의] 이 사진을 설명해 줘.',start_ms:1000,end_ms:2000});
    c.pending=true;phase(c);
    event(c,{type:'session.output_transcript.delta',delta:'[모의] 사진 분석을 연결하는 화면이야. 실제 노을 음성은 연결 후 들을 수 있어!',start_ms:3000,end_ms:5000});
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&current)void stop('화면을 벗어나 노을 대화를 종료했습니다.');});
  window.addEventListener('pagehide',()=>{if(current)void stop();});
  const facade={active:()=>!!current,interrupt,stop,update:s=>{
    shared=s;controls();
    if(current?.id&&current.ready&&!current.closing){
      current.pending=!!s.realtime?.backend_pending;phase(current);
      const photo=s.photo;
      const stamp=photo?.captured_at ? new Date(photo.captured_at).toLocaleTimeString('ko-KR') : '';
      el('rt-frames').textContent=`${photo ? `새 촬영 #${photo.id} · ${stamp}` : '사진은 분석 AI가 처리'} · 이번 세션 분석 ${s.realtime?.backend_calls || 0}회`;
      if(!s.realtime?.active)void stop('서버의 노을 세션이 종료됐습니다.');
    } else if(!current&&s.realtime?.active)status(s.realtime.warning || '다른 화면에서 음성 대화 중');
  }};
  window.BmoLive=facade;window.BmoRealtime=facade;
  if(phone.state())facade.update(phone.state());
})();
