// frontend/src/audio/capture-worklet.js
// AudioWorklet: low-pass filters and decimates the mic stream to 16 kHz and posts PCM16 chunks to the main thread.
// Resampling is done here because browsers may ignore a requested 16 kHz context rate.

import { makeResampler } from "./resample.js";

const TARGET_RATE = 16000;
const CHUNK = 1024; // samples per posted message (64 ms)

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.resample = makeResampler(sampleRate, TARGET_RATE);
    this.out = new Int16Array(CHUNK);
    this.n = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    this.resample(ch, (v) => {
      this.out[this.n++] = v < 0 ? v * 0x8000 : v * 0x7fff;
      if (this.n === CHUNK) {
        const buf = this.out.slice().buffer;
        this.port.postMessage(buf, [buf]);
        this.n = 0;
      }
    });
    return true;
  }
}

registerProcessor("capture", CaptureProcessor);
