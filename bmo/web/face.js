'use strict';
// The supplied JPGs are separate expressions, not consecutive video frames.
// Switch only between compatible expressions during speech; use a brief blink
// for the slower state changes so the face stays recognisable.
(() => {
  const front = document.getElementById('face-frame-a');
  const back = document.getElementById('face-frame-b');
  const player = document.getElementById('player');
  if (!front || !back || !player) return;

  const file = number => `/faces/Rosto-${String(number).padStart(2, '0')}.jpg`;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false;
  let active = front, current = 1, generation = 0, mode = null;
  let motionTimer = null, speechTimer = null, fallbackOpen = false;
  let audioContext = null, analyser = null, samples = null;
  let realtimeAnalyser = null, realtimePlayer = null;
  let emotionKey = null, emotionFrame = null, lastEmotionFrame = null, poseChosen = false;

  // Warm the browser cache for the small set used in live animation.
  if (typeof Image !== 'undefined') {
    for (const number of Array.from({length:25}, (_, index) => index + 1).filter(number => number !== 15)) {
      const image = new Image();
      image.src = file(number);
    }
  }

  function show(number) {
    if (!Number.isInteger(number) || number < 1 || number > 25 || number === 15) number = 1;
    if (current === number) { generation++; return; }
    const incoming = active === front ? back : front;
    const request = ++generation;
    const reveal = () => {
      if (request !== generation || !incoming.naturalWidth || active === incoming) return;
      incoming.classList.add('is-visible');
      active.classList.remove('is-visible');
      active = incoming;
      current = number;
    };
    incoming.onload = reveal;
    incoming.onerror = () => { if (request === generation) incoming.onload = null; };
    incoming.src = file(number);
    if (incoming.complete && incoming.naturalWidth) reveal();
  }

  function stopMotion() {
    clearTimeout(motionTimer);
    clearInterval(speechTimer);
    motionTimer = null;
    speechTimer = null;
  }

  function blink(base) {
    if (reducedMotion || mode !== base.mode) return;
    show(4);
    motionTimer = setTimeout(() => {
      if (mode !== base.mode) return;
      show(base.frame);
      scheduleBlink(base);
    }, 125);
  }

  function scheduleBlink(base) {
    if (reducedMotion) return;
    motionTimer = setTimeout(() => blink(base), 3600 + Math.random() * 2600);
  }

  function volume() {
    const meter = realtimePlayer?.srcObject ? realtimeAnalyser : analyser;
    if (!meter || audioContext?.state !== 'running') return null;
    meter.getByteTimeDomainData(samples);
    let total = 0;
    for (const sample of samples) {
      const amplitude = (sample - 128) / 128;
      total += amplitude * amplitude;
    }
    return Math.sqrt(total / samples.length);
  }

  function speechStep() {
    // Emotional poses stay still for this utterance; the familiar neutral mouth
    // animation remains the fallback instead of cycling unrelated face images.
    if (poseChosen && emotionFrame !== 1) { show(emotionFrame); return; }
    const level = volume();
    if (level === null) {
      fallbackOpen = !fallbackOpen;
      show(fallbackOpen ? 2 : 1);
    } else {
      show(level > 0.025 ? 2 : 1);
    }
  }

  function setMode(next) {
    if (next === mode) return;
    stopMotion();
    mode = next;
    if (next === 'speaking') {
      fallbackOpen = false;
      show(poseChosen ? emotionFrame : 1);
      if (reducedMotion) show(poseChosen ? emotionFrame : 2);
      else speechTimer = setInterval(speechStep, 125);
    } else if (next === 'listening') {
      show(18);
      scheduleBlink({mode: next, frame: 18});
    } else if (next === 'thinking') {
      show(16);
      scheduleBlink({mode: next, frame: 16});
    } else if (next === 'error') {
      show(3);
    } else {
      show(1);
      scheduleBlink({mode: next, frame: 1});
    }
  }

  function beginUtterance(key) {
    if (key === emotionKey) return;
    emotionKey = key; emotionFrame = null; poseChosen = false;
  }

  function setEmotion(label, key) {
    beginUtterance(key);
    if (poseChosen || !window.BmoEmotions) return;
    emotionFrame = window.BmoEmotions.choose(label, lastEmotionFrame);
    lastEmotionFrame = emotionFrame; poseChosen = true;
    if (mode === 'speaking') show(emotionFrame);
  }

  function unlockAudio() {
    const AudioContextType = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextType) return;
    try {
      if (!audioContext) audioContext = new AudioContextType();
      void Promise.resolve(audioContext.resume()).then(() => {
        if (analyser) return;
        const source = audioContext.createMediaElementSource(player);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        samples = new Uint8Array(analyser.fftSize);
        source.connect(analyser);
        analyser.connect(audioContext.destination);
      }).catch(() => {});
    } catch {
      // Playback still works without audio analysis; mouth motion uses a timer.
      analyser = null;
    }
  }

  function unlockRealtimeAudio(element) {
    const AudioContextType = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextType) return;
    try {
      if (!audioContext) audioContext = new AudioContextType();
      void Promise.resolve(audioContext.resume()).then(() => {
        if (realtimeAnalyser) return;
        const source = audioContext.createMediaElementSource(element);
        realtimePlayer = element;
        realtimeAnalyser = audioContext.createAnalyser();
        realtimeAnalyser.fftSize = 256;
        samples = new Uint8Array(256);
        source.connect(realtimeAnalyser);
        realtimeAnalyser.connect(audioContext.destination);
      }).catch(() => {});
    } catch {}
  }
  window.BmoFace = {setMode, beginUtterance, setEmotion, unlockAudio, unlockRealtimeAudio, stop: stopMotion};
  setMode('idle');
})();
