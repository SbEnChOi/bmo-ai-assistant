const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const test = require('node:test');

const code = fs.readFileSync(path.join(__dirname, '../bmo/web/face.js'), 'utf8');
const emotionCode = fs.readFileSync(path.join(__dirname, '../bmo/web/emotions.js'), 'utf8');

function harness({audio=false}={}) {
  let nextTimer = 0;
  const loaded = [];
  const timeouts = new Map(), intervals = new Map();
  class FaceImage {
    constructor() {
      this.classes = new Set();
      this.classList = {add: name => this.classes.add(name), remove: name => this.classes.delete(name)};
      this.complete = false;
      this.naturalWidth = 0;
    }
    set src(value) {
      loaded.push(value);
      this._src = value;
      this.complete = true;
      this.naturalWidth = 1280;
      this.onload?.();
    }
    get src() { return this._src; }
  }
  const front = new FaceImage(), back = new FaceImage();
  front.src = '/faces/Rosto-01.jpg';
  front.classList.add('is-visible');
  const elements = {'face-frame-a': front, 'face-frame-b': back, player: {}};
  const window = {matchMedia: () => ({matches: false})};
  let amplitude = 0;
  if (audio) {
    window.AudioContext = class {
      state = 'running';
      destination = {};
      resume() { return Promise.resolve(); }
      createMediaElementSource() { return {connect() {}}; }
      createAnalyser() { return {fftSize: 256, connect() {}, getByteTimeDomainData(data) { data.fill(128 + amplitude); }}; }
    };
  }
  const context = {
    document: {getElementById: id => elements[id]}, window, Image: FaceImage, Uint8Array, Math, Promise,
    setTimeout: callback => { const id = ++nextTimer; timeouts.set(id, callback); return id; },
    clearTimeout: id => timeouts.delete(id),
    setInterval: callback => { const id = ++nextTimer; intervals.set(id, callback); return id; },
    clearInterval: id => intervals.delete(id),
  };
  vm.runInNewContext(emotionCode, context);
  vm.runInNewContext(code, context);
  return {
    face: window.BmoFace,
    frame: () => [front, back].find(image => image.classes.has('is-visible'))?.src,
    tick: () => [...intervals.values()].forEach(callback => callback()),
    timeout: () => { const [id, callback] = timeouts.entries().next().value; timeouts.delete(id); callback(); },
    intervals,
    loaded, emotions: window.BmoEmotions,
    setAmplitude: value => { amplitude = value; },
  };
}

test('state changes choose attentive and thinking expressions, then return to neutral', () => {
  const h = harness();
  assert.equal(h.frame(), '/faces/Rosto-01.jpg');
  h.face.setMode('listening');
  assert.equal(h.frame(), '/faces/Rosto-18.jpg');
  h.face.setMode('thinking');
  assert.equal(h.frame(), '/faces/Rosto-16.jpg');
  h.face.setMode('idle');
  assert.equal(h.frame(), '/faces/Rosto-01.jpg');
});

test('speech alternates compatible mouth shapes and stops on idle', () => {
  const h = harness();
  h.face.setMode('speaking');
  assert.equal(h.intervals.size, 1);
  h.tick();
  assert.equal(h.frame(), '/faces/Rosto-02.jpg');
  h.tick();
  assert.equal(h.frame(), '/faces/Rosto-01.jpg');
  h.face.setMode('idle');
  assert.equal(h.intervals.size, 0);
});

test('idle blink returns to neutral', () => {
  const h = harness();
  h.timeout();
  assert.equal(h.frame(), '/faces/Rosto-04.jpg');
  h.timeout();
  assert.equal(h.frame(), '/faces/Rosto-01.jpg');
});

test('speech mouth responds to playback volume when audio analysis is available', async () => {
  const h = harness({audio: true});
  h.face.unlockAudio();
  await Promise.resolve();
  h.face.setMode('speaking');
  h.setAmplitude(0);
  h.tick();
  assert.equal(h.frame(), '/faces/Rosto-01.jpg');
  h.setAmplitude(16);
  h.tick();
  assert.equal(h.frame(), '/faces/Rosto-02.jpg');
});

test('emotion pools cover all 24 permitted expressions and never load excluded frames', () => {
  const h=harness();
  const frames=[...new Set(Object.values(h.emotions.frames).flat())].sort((a,b)=>a-b);
  assert.deepEqual(frames,Array.from({length:25},(_,i)=>i+1).filter(n=>n!==15));
  for(const pool of Object.values(h.emotions.frames))assert.ok(pool.length>=2);
  assert.ok(h.loaded.every(src=>!src.includes('Rosto-15') && Number(src.match(/(\d+)\.jpg/)[1])<=25));
});

test('one emotional pose remains stable throughout speech and repeated metadata', () => {
  const h=harness();h.face.setEmotion('기쁨','reply:1');h.face.setMode('speaking');
  const first=h.frame();
  for(let i=0;i<30;i++){h.tick();h.face.setEmotion('슬픔','reply:1');assert.equal(h.frame(),first);}
  assert.ok(h.emotions.frames['기쁨'].some(n=>first.endsWith(String(n).padStart(2,'0')+'.jpg')));
});

test('next reply selects another eligible pose while listening and thinking retain priority', () => {
  const h=harness();h.face.setEmotion('기쁨','one');h.face.setMode('speaking');const first=h.frame();
  h.face.setMode('thinking');assert.equal(h.frame(),'/faces/Rosto-16.jpg');
  h.face.setMode('listening');assert.equal(h.frame(),'/faces/Rosto-18.jpg');
  h.face.setEmotion('슬픔','two');assert.equal(h.frame(),'/faces/Rosto-18.jpg');
  h.face.setMode('speaking');assert.notEqual(h.frame(),first);
  h.face.setMode('idle');assert.equal(h.frame(),'/faces/Rosto-01.jpg');
  h.face.setEmotion('기쁨','three');h.face.setMode('speaking');const third=h.frame();
  h.face.setEmotion('기쁨','four');assert.notEqual(h.frame(),third);
});
