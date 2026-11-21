// frontend/src/audio/capture-worklet.js
// AudioWorklet: averages the mic stream down to 16 kHz and posts PCM16 chunks to the main thread.
// Resampling is done here because browsers may ignore a requested 16 kHz context rate.

const TARGET_RATE = 16000;
const CHUNK = 1024; // samples per posted message (64 ms)

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_RATE;
    this.pos = 0; // fractional read position carried across blocks
    this.sum = 0;
    this.count = 0;
    this.out = new Int16Array(CHUNK);
    this.n = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.sum += ch[i];
      this.count++;
      this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const v = Math.max(-1, Math.min(1, this.sum / this.count));
        this.out[this.n++] = v < 0 ? v * 0x8000 : v * 0x7fff;
        this.sum = 0;
        this.count = 0;
        if (this.n === CHUNK) {
          const buf = this.out.slice().buffer;
          this.port.postMessage(buf, [buf]);
          this.n = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("capture", CaptureProcessor);
