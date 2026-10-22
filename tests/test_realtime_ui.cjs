const fs=require('node:fs'), vm=require('node:vm'), test=require('node:test'), assert=require('node:assert/strict');
const code=fs.readFileSync(require('node:path').join(__dirname,'../bmo/web/realtime.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness({deferMic=false,deferStart=false,deferEmotion=false,deferFrames=false,focus=false}={}) {
  const elements=new Map(), requests=[], handlers={}, sent=[], intervals=new Map(), tracks=[{enabled:true,stop(){this.stopped=true;}}];
  const stream={getTracks:()=>tracks,getAudioTracks:()=>tracks};
  const el=id=>{if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,checked:false,textContent:'',attributes:{},setAttribute(name,value){this.attributes[name]=value;},play:async()=>{},pause(){}});return elements.get(id);};
  let resolveMic, resolveStart, resolveEmotion, resolveFrames, focusCallback, pc, closed=false, counter=0, restored=0, frameResult;
  const emotions=[];
  const dc={readyState:'open',bufferedAmount:0,send:data=>sent.push(JSON.parse(data)),close(){this.readyState='closed';this.onclose?.();}};
  class Peer {
    constructor(){pc=this;this.sctp={maxMessageSize:65536};this.localDescription={sdp:'v=0\r\noffer'};}
    addTrack(){} createDataChannel(){return dc;} async createOffer(){return {sdp:'v=0\r\noffer'};} async setLocalDescription(){} async setRemoteDescription(){dc.onmessage({data:JSON.stringify({type:'session.created'})});} close(){closed=true;}
  }
  const window={isSecureContext:true,RTCPeerConnection:Peer,addEventListener:(name,fn)=>handlers[name]=fn,BmoFace:{setMode(){},beginUtterance(){},setEmotion(label,key){emotions.push({label,key});}},BmoPhone:{state:()=>null,busy:()=>false,prepareRealtime(){},restore(){restored++;},presentPhase(phase,caption){el('response-pending').hidden=phase!=='thinking';el('status').textContent=caption;},
    api:async(path,body)=>{requests.push({path,body});if(path==='realtime/start'){if(deferStart)await new Promise(resolve=>resolveStart=resolve);return {session_id:'owner',sdp:'v=0\r\nanswer',mock:body.mock};}if(path==='realtime/frames')return {version:1,frames:[{caption:'frame #1',image_url:'data:image/jpeg;base64,AA=='},{caption:'frame #2',image_url:'data:image/jpeg;base64,BB=='}]};return {ok:true};}}};
  const originalApi=window.BmoPhone.api;
  if(focus)window.BmoMicFocus={constraints:()=>({autoGainControl:false}),attach:async(s,callback)=>{focusCallback=callback;return {stream:s,supported:true,canInterrupt:()=>true,close:async()=>{}};}};
  window.BmoPhone.api=async(path,body)=>{
    if(path==='realtime/frames'&&deferFrames){requests.push({path,body});await new Promise(resolve=>resolveFrames=resolve);return {version:1,frames:[{caption:'latest',image_url:'data:image/jpeg;base64,AA=='}]};}
    if(path==='realtime/frames' && frameResult){requests.push({path,body});return frameResult;}
    if(path==='realtime/emotion'){
      requests.push({path,body});if(deferEmotion)await new Promise(resolve=>resolveEmotion=resolve);return {emotion:'기쁨'};
    }
    return originalApi(path,body);
  };
  const document={hidden:false,getElementById:el,addEventListener:(name,fn)=>handlers[name]=fn};
  vm.runInNewContext(code,{window,document,RTCPeerConnection:Peer,MediaStream:class{},AbortController,navigator:{mediaDevices:{getUserMedia:()=>deferMic?new Promise(resolve=>resolveMic=resolve):Promise.resolve(stream)}},TextEncoder,performance:{now:()=>1000},
    setTimeout:()=>++counter,clearTimeout(){},setInterval:fn=>{intervals.set(++counter,fn);return counter;},clearInterval:id=>intervals.delete(id),console});
  window.BmoRealtime.update({provider:'openai',realtime:{active:false}});
  return {el,window,document,requests,handlers,sent,tracks,dc,emotions,setFrames:r=>frameResult=r,get pc(){return pc;},closed:()=>closed,restored:()=>restored,resolveMic:()=>resolveMic(stream),resolveStart:()=>resolveStart(),resolveEmotion:()=>resolveEmotion(),resolveFrames:()=>resolveFrames(),focusState:state=>focusCallback(state),tick:()=>[...intervals.values()].forEach(fn=>fn())};
}
test('new voice reply waits for latest frames and creates only once',async()=>{
  const h=harness({deferFrames:true});await h.el('rt-start').onclick();h.el('rt-vision').checked=true;
  const emit=e=>h.dc.onmessage({data:JSON.stringify(e)});
  emit({type:'input_audio_buffer.speech_started'});emit({type:'input_audio_buffer.speech_stopped'});await flush();
  assert.equal(h.sent.some(e=>e.type==='response.create'),false);h.resolveFrames();await flush();await flush();
  const image=h.sent.findIndex(e=>e.type==='conversation.item.create');const reply=h.sent.findIndex(e=>e.type==='response.create');
  assert.ok(image>=0&&reply>image);emit({type:'input_audio_buffer.speech_stopped'});await flush();
  assert.equal(h.sent.filter(e=>e.type==='response.create').length,1);await h.el('rt-stop').onclick();
});
test('silent filter events never cancel an answer when focus bypass is selected',async()=>{
  const h=harness({focus:true});await h.el('rt-start').onclick();
  h.dc.onmessage({data:JSON.stringify({type:'response.created'})});h.dc.onmessage({data:JSON.stringify({type:'output_audio_buffer.started'})});
  h.focusState({active:false,near_ms:0});assert.equal(h.sent.some(e=>e.type==='response.cancel'),false);
  h.focusState({active:true,near_ms:300});assert.equal(h.sent.filter(e=>e.type==='response.cancel').length,1);
  await h.el('rt-stop').onclick();
});
test('mock connection uses no microphone and syncs captions',async()=>{
  const h=harness({deferMic:true});await h.el('rt-mock').onclick();assert.equal(h.window.BmoRealtime.active(),true);
  await h.el('rt-sample').onclick();await flush();h.tick();await flush();
  assert.equal(h.requests[0].body.mock,true);assert.ok(h.requests.some(r=>r.path==='realtime/heartbeat'));assert.equal(h.pc,undefined);
  await h.el('rt-stop').onclick();assert.equal(h.window.BmoRealtime.active(),false);
});
test('real connection supports mute interruption and bounded image items',async()=>{
  const h=harness();await h.el('rt-start').onclick();h.el('rt-mute').onclick();assert.equal(h.tracks[0].enabled,false);
  h.dc.onmessage({data:JSON.stringify({type:'response.created'})});h.dc.onmessage({data:JSON.stringify({type:'output_audio_buffer.started'})});
  h.el('rt-interrupt').onclick();assert.ok(h.sent.some(e=>e.type==='response.cancel'));assert.ok(h.sent.some(e=>e.type==='output_audio_buffer.clear'));
  h.el('rt-vision').checked=true;h.el('rt-vision').onchange();await flush();
  assert.equal(h.sent.filter(e=>e.type==='conversation.item.create').length,2);assert.equal(h.sent.some(e=>e.type==='response.create'),false);
  h.el('rt-vision').checked=false;h.el('rt-vision').onchange();assert.equal(h.sent.filter(e=>e.type==='conversation.item.delete').length,2);
  assert.ok(h.sent.some(e=>e.type==='conversation.item.create' && e.item.content[0].text.includes('시각 입력이 꺼졌')));
  await h.el('rt-stop').onclick();assert.equal(h.tracks[0].stopped,true);assert.equal(h.closed(),true);
});
test('late microphone permission after stop releases tracks without creating a session',async()=>{
  const h=harness({deferMic:true});const start=h.el('rt-start').onclick();await flush();await h.el('rt-stop').onclick();h.resolveMic();await start;
  assert.equal(h.tracks[0].stopped,true);assert.equal(h.requests.some(r=>r.path==='realtime/start'),false);
});
test('late handshake after cancellation is explicitly stopped',async()=>{
  const h=harness({deferStart:true});const start=h.el('rt-start').onclick();await flush();await h.el('rt-stop').onclick();h.resolveStart();await start;
  assert.ok(h.requests.some(r=>r.path==='realtime/stop' && r.body.session_id==='owner'));assert.equal(h.window.BmoRealtime.active(),false);
});
test('hiding the page stops a live session and releases microphone',async()=>{
  const h=harness();await h.el('rt-start').onclick();h.document.hidden=true;h.handlers.visibilitychange();await flush();
  assert.equal(h.tracks[0].stopped,true);assert.equal(h.window.BmoRealtime.active(),false);
});

test('main realtime button starts and stops while preserving push-to-talk exclusion',async()=>{
  const h=harness();assert.equal(h.el('rt-start').textContent,'실시간 대화 시작');
  await h.el('rt-start').onclick();
  assert.equal(h.el('rt-start').textContent,'실시간 대화 종료');
  assert.equal(h.el('rt-start').disabled,false);
  assert.equal(h.el('rt-start').attributes['aria-pressed'],'true');
  assert.equal(h.el('talk').disabled,true);
  await h.el('rt-start').onclick();
  assert.equal(h.window.BmoRealtime.active(),false);
  assert.equal(h.tracks[0].stopped,true);
  assert.equal(h.el('rt-start').textContent,'실시간 대화 시작');
  assert.equal(h.el('rt-start').attributes['aria-pressed'],'false');
});

test('main button cancels microphone permission and releases late input',async()=>{
  const h=harness({deferMic:true});const start=h.el('rt-start').onclick();await flush();
  assert.equal(h.el('rt-start').disabled,false);await h.el('rt-start').onclick();h.resolveMic();await start;
  assert.equal(h.tracks[0].stopped,true);
  assert.equal(h.requests.some(r=>r.path==='realtime/start'),false);
});

test('realtime events show thinking dots and clear them for speech',async()=>{
  const h=harness();await h.el('rt-start').onclick();
  h.dc.onmessage({data:JSON.stringify({type:'input_audio_buffer.speech_stopped'})});
  assert.equal(h.el('response-pending').hidden,false);
  h.dc.onmessage({data:JSON.stringify({type:'output_audio_buffer.started'})});
  assert.equal(h.el('response-pending').hidden,true);
  assert.match(h.el('status').textContent,/이야기 중/);
  await h.el('rt-start').onclick();
});

test('realtime emotion is classified once from the first sentence without holding audio',async()=>{
  const h=harness({deferEmotion:true});await h.el('rt-start').onclick();
  const emit=e=>h.dc.onmessage({data:JSON.stringify(e)});
  emit({type:'response.created',response:{id:'r1'}});emit({type:'output_audio_buffer.started'});
  emit({type:'response.output_audio_transcript.delta',response_id:'r1',delta:'정말 멋져! 성공해서 기뻐!'});
  emit({type:'response.output_audio_transcript.done',response_id:'r1',item_id:'i1',transcript:'정말 멋져! 성공해서 기뻐!'});
  await flush();assert.equal(h.requests.filter(r=>r.path==='realtime/emotion').length,1);
  assert.match(h.el('status').textContent,/이야기 중/);assert.equal(h.emotions.length,0);
  h.resolveEmotion();await flush();assert.equal(h.emotions[0].label,'기쁨');
  await h.el('rt-start').onclick();
});

test('late emotion never changes a newer response or a completed utterance',async()=>{
  for(const finish of ['next','stopped']){
    const h=harness({deferEmotion:true});await h.el('rt-start').onclick();
    const emit=e=>h.dc.onmessage({data:JSON.stringify(e)});
    emit({type:'response.created',response:{id:'r1'}});emit({type:'output_audio_buffer.started'});
    emit({type:'response.output_audio_transcript.delta',response_id:'r1',delta:'정말 멋져! 성공해서 기뻐!'});
    await flush();
    if(finish==='next')emit({type:'response.created',response:{id:'r2'}});
    else emit({type:'output_audio_buffer.stopped'});
    h.resolveEmotion();await flush();assert.equal(h.emotions.length,0);
    await h.el('rt-start').onclick();
  }
});

test('automatic Pi frames require no manual checkbox and never trigger speech',async()=>{
  const h=harness();h.setFrames({version:'auto:1',automatic:true,observation_generation:2,frames:[{caption:'파이 카메라 최신 프레임',image_url:'data:image/jpeg;base64,AA=='}]});
  h.window.BmoRealtime.update({provider:'openai',realtime:{active:false},observation:{enabled:true,generation:2}});
  await h.el('rt-start').onclick();await flush();
  assert.equal(h.el('rt-vision').checked,false);
  assert.equal(h.sent.filter(e=>e.item?.content?.some(c=>c.type==='input_image')).length,1);
  assert.equal(h.sent.some(e=>e.type==='response.create'),false);
  h.setFrames({unchanged:true});h.tick();await flush();
  assert.equal(h.sent.filter(e=>e.type==='conversation.item.delete').length,0);
  h.dc.onmessage({data:JSON.stringify({type:'input_audio_buffer.speech_started'})});await flush();
  assert.equal(h.requests.filter(r=>r.path==='realtime/frames').at(-1).body.force,true);
  h.window.BmoRealtime.update({provider:'openai',realtime:{active:true},observation:{enabled:false,generation:3}});
  h.setFrames({version:'off',frames:[]});h.tick();await flush();
  assert.ok(h.sent.some(e=>e.type==='conversation.item.delete'));
  await h.el('rt-stop').onclick();
});

test('a late automatic image from an earlier settings generation is discarded',async()=>{
  const h=harness();h.setFrames({version:'auto:1',automatic:true,observation_generation:1,frames:[{caption:'old',image_url:'data:image/jpeg;base64,AA=='}]});
  h.window.BmoRealtime.update({provider:'openai',realtime:{active:false},observation:{enabled:true,generation:2}});
  await h.el('rt-start').onclick();await flush();
  assert.equal(h.sent.filter(e=>e.item?.content?.some(c=>c.type==='input_image')).length,0);
  await h.el('rt-stop').onclick();
});
