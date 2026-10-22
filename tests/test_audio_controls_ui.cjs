const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const code=fs.readFileSync(require('node:path').join(__dirname,'../bmo/web/audio-controls.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function harness({deferFirst=false,fail=false}={}) {
  const elements=new Map(),requests=[],timers=new Map();let resolveFirst,serial=0;
  const el=id=>{if(!elements.has(id))elements.set(id,{value:'0',disabled:true,textContent:''});return elements.get(id);};
  const panel={open:true,addEventListener(name,fn){this.toggle=fn;}};
  vm.runInNewContext(code,{document:{getElementById:el,querySelector:()=>panel},Map,Number,Math,
    fetch:async()=>({ok:true,json:async()=>({speaker:{available:true,volume:100},microphone:{available:true,volume:39}})}),
    window:{BmoPhone:{api:async(path,data)=>{requests.push(data);if(deferFirst&&requests.length===1)await new Promise(resolve=>resolveFirst=resolve);if(fail)throw Error('연결 오류');return {[data.device]:{available:true,volume:data.volume,muted:false}};}}},
    setTimeout:fn=>{timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id)});
  panel.toggle();await flush();
  return {el,requests,panel,tick(){const copy=[...timers.values()];timers.clear();copy.forEach(fn=>fn());},resolve:()=>resolveFirst()};
}
test('settings show real levels and plus buttons use independent bounded device volumes',async()=>{
  const h=await harness();assert.equal(h.el('microphone-level').textContent,'39%');
  h.el('microphone-up').onclick();await flush();assert.equal(h.requests[0].volume,44);assert.equal(h.requests[0].device,'microphone');
  h.el('speaker-up').onclick();await flush();assert.equal(h.requests[1].volume,100);
});
test('rapid slider updates keep the newest setting after an older request completes',async()=>{
  const h=await harness({deferFirst:true});
  h.el('microphone-volume').oninput({target:{value:'50'}});h.tick();await flush();
  for(const value of ['55','60','70'])h.el('microphone-volume').oninput({target:{value}});
  h.tick();h.resolve();await flush();
  assert.deepEqual(h.requests.map(r=>r.volume),[50,70]);assert.equal(h.el('microphone-level').textContent,'70%');
});
test('a failed setting restores the last confirmed value and displays the error',async()=>{
  const h=await harness({fail:true});h.el('microphone-up').onclick();await flush();
  assert.equal(Number(h.el('microphone-volume').value),39);assert.match(h.el('audio-settings-status').textContent,/연결 오류/);
});
