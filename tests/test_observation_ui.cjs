const fs=require('node:fs'), vm=require('node:vm'), test=require('node:test'), assert=require('node:assert/strict');
const code=fs.readFileSync(require('node:path').join(__dirname,'../bmo/web/observation.js'),'utf8');
function harness({fail=false}={}) {
  const nodes=new Map(), requests=[];
  const el=id=>{if(!nodes.has(id))nodes.set(id,{checked:false,disabled:false,textContent:''});return nodes.get(id);};
  const state={available:true,enabled:true,proactive:true,fresh:true,memory_count:2,notices_hour:1};
  const window={BmoPhone:{state:()=>({observation:state}),observationChanged:data=>Object.assign(state,data),
    api:async(path,body)=>{requests.push({path,body});if(fail)throw Error('connection lost');return {...state,...body};}}};
  vm.runInNewContext(code,{window,document:{getElementById:el}});
  return {window,el,requests,state};
}
test('observation and initiative are independent settings with no microphone request',async()=>{
  const h=harness();assert.equal(h.el('observe-enabled').checked,true);
  h.el('observe-proactive').checked=false;await h.el('observe-proactive').onchange();
  assert.equal(h.requests[0].body.enabled,true);assert.equal(h.requests[0].body.proactive,false);
  h.el('observe-enabled').checked=false;await h.el('observe-enabled').onchange();
  assert.equal(h.el('observe-proactive').disabled,true);assert.match(h.el('observe-status').textContent,/꺼짐/);
});
test('missing camera disables observation controls',()=>{
  const h=harness();h.window.BmoObservation.update({available:false,enabled:false,proactive:true});
  assert.equal(h.el('observe-enabled').disabled,true);assert.match(h.el('observe-status').textContent,/파이 카메라/);
});
test('a failed setting restores confirmed controls and keeps the error visible',async()=>{
  const h=harness({fail:true});h.el('observe-enabled').checked=false;await h.el('observe-enabled').onchange();
  assert.equal(h.el('observe-enabled').checked,true);assert.equal(h.el('observe-status').textContent,'connection lost');
});
