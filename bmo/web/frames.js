'use strict';
(() => {
  const el = id=>document.getElementById(id), admin=window.BmoAdmin, video=el('webcam-video');
  let stream=null, timer=null, generation=0, uploading=false, urls=[], frameGeneration=0;
  function error(text='') { el('frame-error').textContent=text; }
  function clearPreviews() { for (const url of urls) URL.revokeObjectURL(url); urls=[]; el('frame-preview').replaceChildren(); }
  async function upload(blob, source, label, activate=false, capturedAt=null) {
    const response=await fetch('/api/admin/frames',{method:'POST',headers:{'Content-Type':blob.type,'X-BMO-Token':admin.state()?.token || '', 'X-BMO-Source':source,'X-BMO-Label':encodeURIComponent(label),'X-BMO-Frame-Generation':String(frameGeneration),'X-BMO-Activate':activate?'1':'0',...(capturedAt?{'X-BMO-Captured-At':String(capturedAt)}:{})},body:blob});
    const result=await response.json(); if(!response.ok) throw Error(result.error || '프레임 보관 실패');
    return result;
  }
  function jpegFromCanvas(canvas) { return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('이미지 변환 실패')),'image/jpeg',0.75)); }
  async function prepare(file) {
    if(file.size>20*1024*1024 || !['image/jpeg','image/png'].includes(file.type)) throw Error('20 MB 이하의 JPG 또는 PNG를 선택하세요.');
    const url=URL.createObjectURL(file), image=new Image();
    try {
      await new Promise((resolve,reject)=>{ image.onload=resolve; image.onerror=()=>reject(Error('사진 읽기 실패')); image.src=url; });
      if(image.naturalWidth*image.naturalHeight>16000000) throw Error('16 MP 이하의 사진을 선택하세요.');
      const scale=Math.min(1,960/image.naturalWidth,720/image.naturalHeight), canvas=document.createElement('canvas');
      canvas.width=Math.round(image.naturalWidth*scale); canvas.height=Math.round(image.naturalHeight*scale);
      canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
      return await jpegFromCanvas(canvas);
    } finally { URL.revokeObjectURL(url); }
  }
  function stop() {
    ++generation; clearTimeout(timer); timer=null;
    stream?.getTracks().forEach(t=>t.stop()); stream=null; video.srcObject=null; video.hidden=true;
    el('webcam-start').disabled=false; el('webcam-stop').disabled=true;
  }
  async function collect(id, activate=false) {
    if(id!==generation || !stream) return;
    try {
      if(!video.videoWidth) throw Error('웹캠 화면 준비 중');
      const canvas=document.createElement('canvas'); canvas.width=640; canvas.height=Math.round(640*video.videoHeight/video.videoWidth);
      canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
      const capturedAt=Date.now()/1000;
      const blob=await jpegFromCanvas(canvas);
      if(id!==generation) return;
      await upload(blob,'webcam','PC webcam',activate,capturedAt); activate=false; await admin.refresh();
    } catch(exc) { error(exc.message); }
    if(id===generation) timer=setTimeout(()=>void collect(id,activate),1000);
  }
  el('frame-files').onchange=()=>{ el('frame-upload').disabled=!el('frame-files').files.length || uploading; };
  el('frame-upload').onclick=async()=>{
    if(uploading) return;
    const files=[...el('frame-files').files].sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));
    if(!files.length || files.length>10) { error('사진을 1~10장 선택하세요. 파일 이름이 시간 순서가 되게 준비하세요.'); return; }
    uploading=true; el('frame-upload').disabled=true; stop(); clearPreviews(); error();
    const id=generation;
    try {
      // Decode all files before clearing the previous usable sequence.
      const prepared=[];
      for(const file of files) { prepared.push(await prepare(file)); if(id!==generation) return; }
      const cleared=await admin.api('admin/frames/clear'); frameGeneration=cleared.generation;
      if(id!==generation) return;
      for(let i=0;i<files.length;i++) {
        await upload(prepared[i],'prepared',`${i+1}. ${files[i].name}`,i===0);
        if(id!==generation) return;
        const img=document.createElement('img'), url=URL.createObjectURL(prepared[i]); urls.push(url); img.src=url; img.alt=`${i+1}. ${files[i].name}`; img.title=img.alt; el('frame-preview').append(img);
      }
      await admin.refresh();
    } catch(exc) { error(exc.message); }
    finally { uploading=false; el('frame-upload').disabled=false; }
  };
  el('webcam-start').onclick=async()=>{
    if(stream || uploading) return;
    error(); const id=++generation; el('webcam-start').disabled=true; el('webcam-stop').disabled=false;
    try {
      const acquired=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480}},audio:false});
      if(id!==generation) { acquired.getTracks().forEach(t=>t.stop()); return; }
      stream=acquired; video.srcObject=stream; video.hidden=false; await video.play();
      if(id!==generation) return;
      clearPreviews(); const cleared=await admin.api('admin/frames/clear'); frameGeneration=cleared.generation;
      if(id===generation) void collect(id,true);
    } catch(exc) { if(id===generation) { stop(); error('웹캠 시작 실패: '+exc.message); } }
  };
  el('webcam-stop').onclick=stop;
  el('frames-clear').onclick=async()=>{ stop(); clearPreviews(); try { await admin.api('admin/frames/clear'); await admin.refresh(); } catch(exc) { error(exc.message); } };
  document.addEventListener('visibilitychange',()=>{ if(document.hidden) stop(); });
  window.addEventListener('pagehide',()=>{ stop(); clearPreviews(); });
  window.BmoFrames={update:s=>{
    const f=s.frames; if(!f) return;
    el('frame-status').textContent=`${f.source==='prepared'?'준비된 사진 · 촬영 시각 미확인':stream?'웹캠 수집 중':'웹캠 중지'} · 보관 ${f.count}장 · 사용 가능 ${f.selected}장${f.stale?' · 오래되어 전송하지 않음':''}`;
  }};
})();
