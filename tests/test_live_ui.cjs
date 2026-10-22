const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const code=fs.readFileSync(require('node:path').join(__dirname,'../bmo/web/live.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness({mode='live',deferMic=false,deferStart=false,iceComplete=true,deferEmotion=false}={}) {
  const elements=new Map(),requests=[],sent=[],handlers={},intervals=new Map(),timers=new Map(),emotions=[];
  const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:false,checked:false,paused:true,attributes:{},setAttribute(k,v){this.attributes[k]=v;},async play(){this.paused=false;},pause(){this.paused=true;}});return elements.get(id);};
  const tracks=[{enabled:true,stop(){this.stopped=true;}}],stream={getTracks:()=>tracks,getAudioTracks:()=>tracks};
  let resolveMic,resolveStart,resolveEmotion,pc,counter=0,micCalls=0,now=1000,level=128;
  const dc={readyState:'open',send:raw=>sent.push(JSON.parse(raw)),close(){this.readyState='closed';this.onclose?.();}};
  const emit=ev=>dc.onmessage({data:JSON.stringify(ev)});
  class Peer {
    constructor(){pc=this;this.iceGatheringState=iceComplete?'complete':'gathering';this.listeners={};this.localDescription={sdp:'v=0\r\noffer'};}
    addTrack(){}createDataChannel(name){assert.equal(name,'oai-events');return dc;}
    async createOffer(){return this.localDescription;}async setLocalDescription(){}
    async setRemoteDescription(){emit({type:'session.started'});}
    addEventListener(k,fn){this.listeners[k]=fn;}removeEventListener(k){delete this.listeners[k];}
    close(){this.closed=true;}
  }
  class Context {
    state='running';async resume(){}async close(){this.state='closed';}
    createMediaStreamSource(){return {connect(){}};}
    createAnalyser(){return {getByteTimeDomainData:a=>a.fill(level)};}
  }
  const window={isSecureContext:true,RTCPeerConnection:Peer,AudioContext:Context,addEventListener:(k,v)=>handlers[k]=v,
    BmoFace:{beginUtterance(){},setEmotion:(label,key)=>emotions.push({label,key}),unlockRealtimeAudio(){}},
    BmoPhone:{state:()=>null,busy:()=>false,prepareRealtime(){},restore(){},presentPhase:(p,t)=>{el('response-pending').hidden=p!=='thinking';el('status').textContent=t;},
      api:async(path,body)=>{requests.push({path,body});
        if(path==='live/start'){if(deferStart)await new Promise(r=>resolveStart=r);return {session_id:'owner',sdp:'v=0\r\nanswer'};}
        if(path==='live/emotion'){if(deferEmotion)await new Promise(r=>resolveEmotion=r);return {emotion:'기쁨'};}
        return {ok:true};}}};
  const document={hidden:false,querySelector:()=>({content:mode}),getElementById:el,addEventListener:(k,v)=>handlers[k]=v};
  vm.runInNewContext(code,{window,document,RTCPeerConnection:Peer,MediaStream:class{},Uint8Array,AbortController,
    navigator:{mediaDevices:{getUserMedia:()=>{micCalls++;return deferMic?new Promise(r=>resolveMic=r):Promise.resolve(stream);}}},
    performance:{now:()=>now},setInterval:fn=>{intervals.set(++counter,fn);return counter;},clearInterval:id=>intervals.delete(id),
    setTimeout:(fn,ms)=>{timers.set(++counter,{fn,ms});return counter;},clearTimeout:id=>timers.delete(id)});
  window.BmoLive?.update({provider:'openai',realtime:{active:false}});
  return {window,document,el,requests,sent,handlers,tracks,dc,emotions,timers,emit,get pc(){return pc;},get micCalls(){return micCalls;},
    resolveMic:()=>resolveMic(stream),resolveStart:()=>resolveStart(),resolveEmotion:()=>resolveEmotion(),
    tick:()=>[...intervals.values()].forEach(fn=>fn()),setLevel:v=>level=v,advance:ms=>now+=ms};
}
test('legacy page never installs Live handlers',()=>{assert.equal(harness({mode:'realtime'}).window.BmoLive,undefined);});
test('mock keeps PTT exclusion but uses no microphone or WebRTC',async()=>{
  const h=harness();await h.el('rt-mock').onclick();assert.equal(h.micCalls,0);assert.equal(h.pc,undefined);
  assert.equal(h.el('talk').disabled,true);h.el('rt-sample').onclick();await flush();
  assert.match(h.el('live-input').textContent,/모의/);assert.match(h.el('live-output').textContent,/모의/);
  assert.equal(h.sent.length,0);await h.el('rt-stop').onclick();assert.equal(h.window.BmoLive.active(),false);
});
test('Live uses session.started, exact independent transcript fragments, and cumulative usage',async()=>{
  const h=harness();await h.el('rt-start').onclick();assert.equal(h.sent.some(e=>e.type==='session.start'),false);
  h.emit({type:'session.input_transcript.delta',event_id:'u1',delta:'안녕 ',start_ms:0,end_ms:500});
  h.emit({type:'session.output_transcript.delta',event_id:'a1',delta:'반가워 ',start_ms:500,end_ms:600});
  h.emit({type:'session.input_transcript.delta',event_id:'u2',delta:'안녕',start_ms:500,end_ms:900});
  h.emit({type:'session.input_transcript.delta',event_id:'u2',delta:'안녕',start_ms:500,end_ms:900});
  assert.equal(h.el('live-input').textContent,'내 말: 안녕 안녕');assert.equal(h.el('live-output').textContent,'BMO: 반가워 ');
  assert.doesNotMatch(h.el('status').textContent,/이야기 중/); // transcript does not prove playback
  h.emit({type:'session.usage.updated',usage:{seconds:12}});h.emit({type:'session.usage.updated',usage:{seconds:15}});
  assert.match(h.el('rt-metrics').textContent,/15초/);assert.doesNotMatch(h.el('rt-metrics').textContent,/27초/);
  await h.el('rt-stop').onclick();assert.equal(h.tracks[0].stopped,true);assert.equal(h.pc.closed,true);
});
test('mute and interruption use Live events, not Realtime response commands',async()=>{
  const h=harness();await h.el('rt-start').onclick();h.el('rt-mute').onclick();assert.equal(h.tracks[0].enabled,false);
  h.el('rt-interrupt').onclick();assert.ok(h.sent.some(e=>e.type==='session.input_audio.mute'));
  assert.ok(h.sent.some(e=>e.type==='session.instructions.append'));assert.equal(h.sent.some(e=>e.type==='response.cancel'),false);
  assert.equal(h.el('rt-player').muted,true);await h.el('rt-stop').onclick();
});
test('ICE completes before starting a paid remote session',async()=>{
  const h=harness({iceComplete:false});const start=h.el('rt-start').onclick();await flush();
  assert.equal(h.requests.some(r=>r.path==='live/start'),false);
  h.pc.iceGatheringState='complete';h.pc.listeners.icegatheringstatechange();await start;
  assert.equal(h.requests.filter(r=>r.path==='live/start').length,1);await h.el('rt-stop').onclick();
});
test('stop during microphone permission releases late tracks without API start',async()=>{
  const h=harness({deferMic:true});const start=h.el('rt-start').onclick();await flush();await h.el('rt-start').onclick();
  h.resolveMic();await start;assert.equal(h.tracks[0].stopped,true);assert.equal(h.requests.some(r=>r.path==='live/start'),false);
});
test('cancelled handshake explicitly closes the late server session',async()=>{
  const h=harness({deferStart:true});const start=h.el('rt-start').onclick();await flush();await h.el('rt-start').onclick();
  h.resolveStart();await start;assert.ok(h.requests.some(r=>r.path==='live/stop'&&r.body.session_id==='owner'));
});
test('backend waiting shows thinking and actual output level chooses speech emotion',async()=>{
  const h=harness({deferEmotion:true});await h.el('rt-start').onclick();h.pc.ontrack({streams:[{}]});
  h.emit({type:'session.delegation.created'});assert.equal(h.el('response-pending').hidden,false);
  h.emit({type:'session.output_transcript.delta',delta:'정말 멋져! 함께 성공해서 기뻐!',start_ms:0,end_ms:1000});
  await flush();assert.equal(h.emotions.length,0);h.resolveEmotion();await flush();assert.equal(h.emotions.length,0);
  h.setLevel(150);h.tick();assert.match(h.el('status').textContent,/이야기 중/);assert.equal(h.emotions[0].label,'기쁨');
  h.setLevel(128);h.advance(500);h.tick();assert.doesNotMatch(h.el('status').textContent,/이야기 중/);await h.el('rt-stop').onclick();
});
test('visibility exit closes the server session and microphone',async()=>{
  const h=harness();await h.el('rt-start').onclick();h.document.hidden=true;h.handlers.visibilitychange();await flush();
  assert.equal(h.tracks[0].stopped,true);assert.ok(h.requests.some(r=>r.path==='live/stop'));assert.equal(h.window.BmoLive.active(),false);
});
test('broken data channel still stops the server and cleans up peer resources',async()=>{
  const h=harness();await h.el('rt-start').onclick();h.dc.send=()=>{throw Error('OperationError');};
  await h.el('rt-stop').onclick();assert.ok(h.requests.some(r=>r.path==='live/stop'));
  assert.equal(h.pc.closed,true);assert.equal(h.window.BmoLive.active(),false);assert.equal(h.tracks[0].stopped,true);
});
