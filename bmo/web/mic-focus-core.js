'use strict';
// Shared by AudioWorklet and synthetic PCM tests; no browser or network access.
globalThis.BmoFocusGate = class {
  constructor(rate=48000) {
    this.rate=rate;this.delay=new Float32Array(Math.ceil(rate*.18));this.position=0;
    this.attack=0;this.hold=0;this.active=false;this.gain=0;this.noise=.001;
    this.enabled=true;this.sensitivity=.65;this.nearMs=0;this.level=0;
  }
  configure(options={}) {
    if(typeof options.enabled==='boolean')this.enabled=options.enabled;
    if(Number.isFinite(options.sensitivity))this.sensitivity=Math.max(0,Math.min(1,options.sensitivity));
  }
  process(input, output) {
    let power=0;for(const v of input)power+=v*v;
    this.level=Math.sqrt(power/Math.max(1,input.length));
    const count=input.length, threshold=Math.max(.012+(1-this.sensitivity)*.055,this.noise*3);
    if(!this.active&&this.level<threshold*.75)this.noise=this.noise*.995+this.level*.005;
    const strong=this.level>=threshold;
    const sustaining=this.active&&this.level>=Math.max(threshold*.25,this.noise*1.6);
    if(strong){this.attack+=count;}
    else this.attack=0;
    if(strong||sustaining)this.nearMs+=count/this.rate*1000;
    else if(this.hold<=0)this.nearMs=0;
    if(this.attack>=this.rate*.08||sustaining){this.active=true;this.hold=Math.ceil(this.rate*.32);}
    else if(this.hold>0){this.hold-=count;}
    else this.active=false;
    const target=!this.enabled||this.active?1:0;
    for(let i=0;i<output.length;i++) {
      const old=this.delay[this.position];this.delay[this.position]=input[i]||0;
      this.position=(this.position+1)%this.delay.length;
      this.gain+=Math.max(-1/(this.rate*.02),Math.min(1/(this.rate*.005),target-this.gain));
      output[i]=this.enabled?old*this.gain:(input[i]||0);
    }
    return {active:this.active,near_ms:this.nearMs,level:this.level,threshold};
  }
};
