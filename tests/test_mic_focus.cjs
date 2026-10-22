const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const scope={Float32Array};vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../bmo/web/mic-focus-core.js'),'utf8'),scope);
const rate=16000,block=160;
function feed(g,amp,ms){const result=[];let state;for(let t=0;t<ms;t+=10){const input=new Float32Array(block),out=new Float32Array(block);for(let i=0;i<block;i++)input[i]=amp*Math.sin(2*Math.PI*250*i/rate);state=g.process(input,out);result.push(...out);}return {state,samples:result};}
test('quiet background and short impact do not open the gate',()=>{
  const g=new scope.BmoFocusGate(rate);assert.equal(feed(g,.007,1000).state.active,false);
  assert.equal(feed(g,.5,30).state.active,false);assert.equal(feed(g,.007,400).state.active,false);
});
test('close speech opens after sustained audio and retains the first syllable',()=>{
  const g=new scope.BmoFocusGate(rate);feed(g,0,250);const speech=feed(g,.12,400);
  assert.equal(speech.state.active,true);assert.ok(speech.samples.slice(2880,3200).some(v=>Math.abs(v)>.05));
  assert.ok(speech.state.near_ms>=240);
});
test('brief pauses retain the phrase, silence closes, and sensitivity can be adjusted',()=>{
  const g=new scope.BmoFocusGate(rate);feed(g,.12,400);assert.equal(feed(g,0,200).state.active,true);
  assert.equal(feed(g,0,400).state.active,false);g.configure({sensitivity:.2});assert.equal(feed(g,.05,300).state.active,false);
  g.configure({sensitivity:.9});assert.equal(feed(g,.05,300).state.active,true);
});
test('bypass preserves original audio and configured values are bounded',()=>{
  const g=new scope.BmoFocusGate(rate);g.configure({enabled:false,sensitivity:200});assert.equal(g.sensitivity,1);
  const output=feed(g,.01,30).samples;assert.ok(output.some(v=>Math.abs(v)>.005));
});
test('near voice confirmation accumulates across ordinary syllable gaps',()=>{
  const g=new scope.BmoFocusGate(rate);let longest=0;
  for(let i=0;i<10;i++){const voice=feed(g,.12,150);longest=Math.max(longest,voice.state.near_ms);feed(g,0,50);}
  assert.ok(longest>=240);feed(g,0,600);assert.equal(g.nearMs,0);
});
test('a softer continuation after loud onset is retained without opening for quiet background alone',()=>{
  const g=new scope.BmoFocusGate(rate);assert.equal(feed(g,.02,800).state.active,false);
  feed(g,.12,180);const continuation=feed(g,.02,1200);
  assert.equal(continuation.state.active,true);assert.ok(continuation.samples.slice(-1600).some(v=>Math.abs(v)>.01));
});
