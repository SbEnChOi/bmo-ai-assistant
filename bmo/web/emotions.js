'use strict';
(() => {
  const frames = {
    '평온': [1,4,18], '기쁨': [2,5,13,20,23], '애정': [5,13,19,21],
    '장난': [14,18,19], '감동': [5,6,13,21], '슬픔': [3,6,11,12],
    '걱정': [3,6,9], '화남': [7,10], '불만': [8,9,16],
    '놀람': [13,17,22,23], '혼란': [17,22,24], '지침': [8,24,25]
  };
  const normalize = label => Object.hasOwn(frames, label) ? label : '평온';
  function choose(label, previous) {
    const pool = frames[normalize(label)];
    const choices = pool.filter(frame => frame !== previous);
    return choices[Math.floor(Math.random() * choices.length)];
  }
  Object.values(frames).forEach(Object.freeze);
  window.BmoEmotions = Object.freeze({frames:Object.freeze(frames), normalize, choose});
})();
