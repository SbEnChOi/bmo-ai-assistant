// Deterministic client behavior tests, without a physical microphone or Safari.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const code = fs.readFileSync(require('node:path').join(__dirname, '../bmo/web/phone.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function proactive(id, seconds=20) {return {id,text:'컵을 가져왔네! 뭐 마시고 있어?',audio_ready:true,kind:'proactive',expires_at:Date.now()/1000+seconds,observation_generation:2,emotion:'기쁨'};}

test('fresh proactive speech plays through the existing player and emotion path',async()=>{
  const h=await harness();h.state.observation={enabled:true,proactive:true,generation:2};
  h.state.reply_id=1;h.state.replies=[proactive(1)];await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,1);assert.equal(h.emotions[0].label,'기쁨');
  h.state.observation.proactive=false;h.state.observation.generation=3;await h.context.refresh();
  assert.equal(h.context.window.BmoPhone.busy(),false);
});
test('expired or disabled proactive notices never play while normal answers still work',async()=>{
  const h=await harness();h.state.observation={enabled:true,proactive:true,generation:2};
  h.state.reply_id=1;h.state.replies=[proactive(1,-1)];await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,0);
  h.state.observation.proactive=false;h.state.reply_id=2;h.state.replies=[proactive(2)];await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,0);
  h.state.reply_id=3;h.state.replies=[{id:3,text:'사용자 질문에 대한 답변',audio_ready:true}];await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,1);
});
test('a notice arriving while the user records is dropped instead of queued for later',async()=>{
  const h=await harness();h.state.observation={enabled:true,proactive:true,generation:2};await h.context.refresh();
  await h.element('talk').onclick();h.state.reply_id=1;h.state.replies=[proactive(1)];await h.context.refresh();
  h.advance(1000);await h.element('talk').onclick();await flush();
  assert.equal(h.element('player').playCount,0);
  assert.ok(h.requests.some(r=>r.url==='/api/phone/activity' && JSON.parse(r.body).phase==='permission'));
});

async function harness({deferMic=false,deferVoice=false,initialReply=null,rejectPlays=0}={}) {
  const elements = new Map(), handlers = {}, requests = [], emotions=[];
  function element(id) {
    if (!elements.has(id)) elements.set(id,{id,value:'',textContent:'',disabled:false,hidden:false,dataset:{},playCount:0,
      classList:{toggle(){},remove(){},add(){}},setAttribute(){},removeAttribute(){},load(){},pause(){},
      async play(){this.playCount++;if(rejectPlays>0){rejectPlays--;throw new Error('NotAllowedError');}this.onplaying?.();}});
    return elements.get(id);
  }
  const state={provider:'openai',voice_ready:true,busy:false,phase:'idle',token:'test',scene_mode:'off',reply_id:0,last_reply:'',audio_ready:false,replies:[]};
  if(initialReply){state.reply_id=initialReply.id;state.last_reply=initialReply.text;state.audio_ready=initialReply.audio_ready;state.replies=[initialReply];}
  const track={stopped:false,stop(){this.stopped=true;}}, stream={getTracks:()=>[track]};
  let resolveMic, resolveVoice, now=0;
  class Recorder {
    static isTypeSupported(mime){return mime==='audio/mp4';}
    constructor(stream,options){this.mimeType=options.mimeType;this.state='inactive';}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['x'.repeat(200)],{type:this.mimeType})});queueMicrotask(()=>this.onstop?.());}
  }
  const document={hidden:false,getElementById:element,addEventListener:(name,fn)=>{handlers[name]=fn;}};
  const context=vm.createContext({document,navigator:{mediaDevices:{getUserMedia:()=>deferMic?new Promise(resolve=>{resolveMic=resolve;}):Promise.resolve(stream)}},
    window:{isSecureContext:true,MediaRecorder:Recorder,BmoFace:{setMode(){},unlockAudio(){},setEmotion(label,key){emotions.push({label,key});}},addEventListener:(name,fn)=>{handlers[name]=fn;}},MediaRecorder:Recorder,
    Blob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},AbortController,Uint8Array,atob,performance:{now:()=>now},console,queueMicrotask,
    setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},
    fetch:async(url,options)=>{if(url.startsWith('/api/audio/'))return {ok:true,blob:async()=>new Blob(['mp3'])};if(!options)return {ok:true,status:200,json:async()=>state};requests.push({url,...options});if(url==='/api/voice'&&deferVoice)await new Promise(resolve=>resolveVoice=resolve);return {ok:true,status:200,json:async()=>url==='/api/voice'?{question:'안녕',reply:'반가워',reply_id:state.reply_id}:{ok:true}};}});
  vm.runInContext(code,context);await flush();
  return {element,requests,track,state,document,handlers,context,emotions,advance:ms=>{now+=ms;},resolveMic:()=>resolveMic(stream),resolveVoice:()=>resolveVoice()};
}

test('tap twice records MP4, uploads once and releases microphone',async()=>{
  const h=await harness();await h.element('talk').onclick();assert.equal(h.element('talk-label').textContent,'다시 눌러 보내기');
  h.advance(1000);await h.element('talk').onclick();await flush();
  const uploads=h.requests.filter(r=>r.url==='/api/voice');assert.equal(uploads.length,1);assert.equal(uploads[0].body.type,'audio/mp4');assert.equal(h.track.stopped,true);
});
test('phone sends the shared image mode with voice',async()=>{
  const h=await harness();h.state.scene_mode='upload';await h.context.refresh();await h.element('talk').onclick();h.advance(1000);await h.element('talk').onclick();await flush();
  assert.equal(h.requests.find(r=>r.url==='/api/voice').headers['X-BMO-Camera'],'1');
});
test('cancel recording never uploads',async()=>{
  const h=await harness();await h.element('talk').onclick();h.advance(1000);await h.element('cancel').onclick();await flush();
  assert.equal(h.requests.some(r=>r.url==='/api/voice'),false);assert.equal(h.track.stopped,true);
});
test('late microphone permission after cancel releases stream',async()=>{
  const h=await harness({deferMic:true});const start=h.element('talk').onclick();await flush();await h.element('cancel').onclick();h.resolveMic();await start;await flush();
  assert.equal(h.track.stopped,true);assert.equal(h.requests.some(r=>r.url==='/api/voice'),false);
});
test('short recording is rejected without upload',async()=>{
  const h=await harness();await h.element('talk').onclick();h.advance(100);await h.element('talk').onclick();await flush();
  assert.match(h.element('error').textContent,/짧아/);assert.equal(h.requests.some(r=>r.url==='/api/voice'),false);
});
test('hiding page cancels capture without upload',async()=>{
  const h=await harness();await h.element('talk').onclick();h.advance(1000);h.document.hidden=true;h.handlers.visibilitychange();await flush();
  assert.equal(h.track.stopped,true);assert.equal(h.requests.some(r=>r.url==='/api/voice'),false);
});
test('PC reply is picked up and played on phone',async()=>{
  const h=await harness();h.state.reply_id=1;h.state.last_reply='PC에서 보낸 질문의 답';h.state.audio_ready=true;h.state.replies=[{id:1,text:h.state.last_reply,audio_ready:true}];await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,1);assert.equal(h.element('replay').hidden,false);assert.equal(h.element('transcript').textContent,'PC에서 보낸 질문의 답');
});
test('phone plays PC replies that arrived while recording',async()=>{
  const h=await harness();await h.element('talk').onclick();
  h.state.reply_id=1;h.state.replies=[{id:1,text:'PC 답변',audio_ready:true}];await h.context.refresh();
  assert.equal(h.element('player').playCount,0);
  h.advance(1000);await h.element('talk').onclick();await flush();
  assert.equal(h.element('player').playCount,1);
});

test('opening phone after a PC answer preloads only the latest reply and waits for a tap',async()=>{
  const h=await harness({initialReply:{id:4,text:'이미 생성된 카메라 답변',audio_ready:true}});
  assert.equal(h.element('player').playCount,0);
  assert.equal(h.element('replay').hidden,false);
  assert.equal(h.element('transcript').textContent,'이미 생성된 카메라 답변');
  await h.element('enable-sound').onclick();
  assert.equal(h.element('player').playCount,1);
  assert.equal(h.element('enable-sound').hidden,true);
});

test('blocked automatic audio can be started from the explicit sound button',async()=>{
  const h=await harness({rejectPlays:1});
  h.state.reply_id=1;h.state.replies=[{id:1,text:'PC 답변',audio_ready:true}];
  await h.context.refresh();await flush();
  assert.equal(h.element('enable-sound').hidden,false);
  assert.match(h.element('error').textContent,/소리 켜기/);
  await h.element('enable-sound').onclick();
  assert.equal(h.element('player').playCount,2);
  assert.equal(h.element('enable-sound').hidden,true);
  assert.equal(h.element('error').textContent,'');
});

test('enabling sound without a reply plays a local tone without recording or API requests',async()=>{
  const h=await harness();await h.element('enable-sound').onclick();
  assert.equal(h.element('player').playCount,1);
  assert.equal(h.requests.length,0);
  assert.equal(h.element('talk-label').textContent,'눌러서 말하기');
  h.element('player').onended();
  assert.equal(h.element('replay').hidden,true);
});

test('a PC reply arriving during the sound check waits for the tone to end',async()=>{
  const h=await harness();await h.element('enable-sound').onclick();
  h.state.reply_id=1;h.state.replies=[{id:1,text:'소리 확인 중 도착한 답변',audio_ready:true}];
  await h.context.refresh();await flush();
  assert.equal(h.element('player').playCount,1);
  h.element('player').onended();await flush();
  assert.equal(h.element('player').playCount,2);
  assert.equal(h.element('transcript').textContent,'소리 확인 중 도착한 답변');
});

test('pending voice request follows server processing phases and clears on cancellation',async()=>{
  const h=await harness({deferVoice:true});await h.element('talk').onclick();
  h.advance(1000);await h.element('talk').onclick();await flush();
  assert.equal(h.element('response-pending').hidden,false);
  h.state.busy=true;
  for(const phase of ['capturing','thinking','synthesizing']){
    h.state.phase=phase;await h.context.refresh();
    assert.equal(h.element('face').dataset.state,'thinking');
    assert.equal(h.element('response-pending').hidden,false);
  }
  h.state.busy=false;await h.element('cancel').onclick();h.resolveVoice();await flush();
  assert.equal(h.element('response-pending').hidden,true);
  assert.equal(h.element('talk-label').textContent,'눌러서 말하기');
});

test('PC and shared realtime processing show the same pending indicator, then clear for playback',async()=>{
  const h=await harness();h.state.busy=true;h.state.phase='thinking';await h.context.refresh();
  assert.equal(h.element('response-pending').hidden,false);
  h.state.busy=false;h.state.realtime={active:true,phase:'thinking'};await h.context.refresh();
  assert.equal(h.element('face').dataset.state,'thinking');
  assert.equal(h.element('response-pending').hidden,false);
  h.state.realtime.phase='speaking';await h.context.refresh();
  assert.equal(h.element('response-pending').hidden,true);
  assert.equal(h.element('face').dataset.state,'speaking');
});

test('reply emotion is applied when its audio plays, not when an old reply is preloaded',async()=>{
  const h=await harness({initialReply:{id:8,text:'축하해!',audio_ready:true,emotion:'기쁨'}});
  assert.equal(h.emotions.length,0);await h.element('enable-sound').onclick();
  assert.equal(h.emotions[0].label,'기쁨');assert.equal(h.emotions[0].key,'reply:8');
  assert.equal(h.element('transcript').textContent,'축하해!');
});
