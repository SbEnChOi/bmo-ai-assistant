'use strict';
(() => {
  const el=id=>document.getElementById(id);
  let enabled=true,sensitivity=.65,connection=null;
  try {
    const saved=JSON.parse(localStorage.getItem('bmo-mic-focus')||'null');
    if(typeof saved?.enabled==='boolean')enabled=saved.enabled;
    if(Number.isFinite(saved?.sensitivity))sensitivity=Math.max(.2,Math.min(.9,saved.sensitivity));
  }catch{}
  function label(text){if(el('mic-focus-status'))el('mic-focus-status').textContent=text;}
  function settings(){
    if(el('mic-focus-enabled'))el('mic-focus-enabled').checked=enabled;
    if(el('mic-focus-sensitivity'))el('mic-focus-sensitivity').value=Math.round(sensitivity*100);
    if(el('mic-focus-value'))el('mic-focus-value').textContent=Math.round(sensitivity*100)+'%';
  }
  function update(){
    enabled=el('mic-focus-enabled').checked;sensitivity=Number(el('mic-focus-sensitivity').value)/100;
    try{localStorage.setItem('bmo-mic-focus',JSON.stringify({enabled,sensitivity}));}catch{}
    connection?.node.port.postMessage({enabled,sensitivity});settings();
    if(!connection)label(enabled?'가까운 목소리 우선 · 대화를 시작하면 작동해요.':'가까운 목소리 필터 꺼짐');
  }
  async function attach(stream,onState=()=>{},signal) {
    let context,node,source,filter,destination,closed=false;
    const state={active:false,near_ms:0,level:0};
    async function bounded(promise,ms){
      let timer,abort;
      try{return await Promise.race([promise,new Promise((_,reject)=>{
        timer=setTimeout(()=>reject(Error('focus timeout')),ms);
        abort=()=>reject(Error('focus aborted'));
        if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
      })]);}finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
    }
    async function close(){
      if(closed)return;closed=true;
      if(connection?.node===node)connection=null;
      try{source?.disconnect();filter?.disconnect();node?.disconnect();}catch{}
      destination?.stream.getTracks().forEach(t=>t.stop());
      try{await context?.close();}catch{}
    }
    const result={stream,supported:false,state,close,canInterrupt:()=>!enabled||(result.supported&&state.active&&state.near_ms>=240)};
    try{
      const Context=window.AudioContext||window.webkitAudioContext;
      if(!Context||!window.AudioWorkletNode)throw Error('unsupported');
      context=new Context();await bounded(context.resume(),1500);
      if(!context.audioWorklet)throw Error('unsupported');
      await bounded(context.audioWorklet.addModule('/mic-focus-worklet.js'),2500);
      if(signal?.aborted)throw Error('focus aborted');
      source=context.createMediaStreamSource(stream);filter=context.createBiquadFilter();filter.type='highpass';filter.frequency.value=110;
      node=new AudioWorkletNode(context,'bmo-mic-focus',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});
      destination=context.createMediaStreamDestination();source.connect(filter);filter.connect(node);node.connect(destination);
      node.port.postMessage({enabled,sensitivity});
      node.port.onmessage=e=>{
        if(closed)return;
        Object.assign(state,e.data);
        label(!enabled?'필터 꺼짐':state.active?'가까운 목소리를 듣고 있어요.':'주변 소리 차단 중 · 마이크 가까이 말해 주세요.');
        onState(state);
      };
      node.onprocessorerror=()=>{if(!closed){result.supported=false;label('입력 필터 오류 · 대화를 다시 시작해 주세요.');onState({failed:true,active:false});void close();}};
      result.stream=destination.stream;result.supported=true;connection={node};
      label('가까운 목소리 필터 작동 중');
    }catch{
      await close();result.close=async()=>{};
      label('입력 필터 미지원 · 자동 끼어들기는 제한돼요. 말 멈추기 버튼을 사용하세요.');
    }
    return result;
  }
  settings();
  if(el('mic-focus-enabled'))el('mic-focus-enabled').onchange=update;
  if(el('mic-focus-sensitivity'))el('mic-focus-sensitivity').oninput=update;
  window.BmoMicFocus={attach,constraints:()=>({echoCancellation:true,noiseSuppression:true,autoGainControl:false,channelCount:1})};
})();
