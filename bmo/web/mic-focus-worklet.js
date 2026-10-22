import './mic-focus-core.js';
class BmoFocusProcessor extends AudioWorkletProcessor {
  constructor(){super();this.gate=new globalThis.BmoFocusGate(sampleRate);this.samples=0;this.previous=false;
    this.port.onmessage=e=>this.gate.configure(e.data);}
  process(inputs,outputs){
    const output=outputs[0]?.[0];if(!output)return true;
    const input=inputs[0]?.[0]||new Float32Array(output.length);
    const state=this.gate.process(input,output);this.samples+=output.length;
    if(this.samples>=sampleRate*.04||state.active!==this.previous){
      this.port.postMessage(state);this.samples=0;this.previous=state.active;
    }
    return true;
  }
}
registerProcessor('bmo-mic-focus',BmoFocusProcessor);
