// frontend/src/audio/resample.js
// Streaming windowed-sinc low-pass + resampler (any input rate -> 16 kHz). The cutoff sits at 0.45 * target
// rate (7.2 kHz for 16 kHz) so nothing above the target Nyquist (8 kHz) aliases into the speech band.
// Non-integer ratios (44.1 kHz) are handled by evaluating the filter at fractional positions.

const HALF_TAPS = 24; // taps per side, measured in input samples at ratio 1; scaled up for higher input rates

/** Returns push(samples: Float32Array, emit: (v: number) => void) that emits clamped output samples in [-1, 1]. */
export function makeResampler(inRate, outRate) {
  const ratio = inRate / outRate;
  const cutoff = (0.45 * outRate) / inRate; // cycles per input sample
  const half = Math.ceil(HALF_TAPS * Math.max(1, ratio));
  let hist = new Float32Array(0); // unconsumed input
  let pos = 0; // next output centre, in samples relative to hist[0]
  const kernel = (x) => {
    const sinc = x === 0 ? 2 * cutoff : Math.sin(2 * Math.PI * cutoff * x) / (Math.PI * x);
    const w = 0.42 + 0.5 * Math.cos((Math.PI * x) / half) + 0.08 * Math.cos((2 * Math.PI * x) / half); // Blackman
    return sinc * w;
  };
  // Integer ratios (48 kHz -> 16 kHz) always land on whole samples: precompute the taps once.
  const taps = Number.isInteger(ratio) ? Float64Array.from({ length: 2 * half }, (_, k) => kernel(k - half + 1)) : null;
  return function push(samples, emit) {
    const buf = new Float32Array(hist.length + samples.length);
    buf.set(hist);
    buf.set(samples, hist.length);
    while (pos + half < buf.length) {
      const centre = Math.floor(pos);
      let acc = 0;
      for (let i = centre - half + 1; i <= centre + half; i++) {
        if (i >= 0) acc += buf[i] * (taps ? taps[i - centre + half - 1] : kernel(i - pos));
      }
      emit(Math.max(-1, Math.min(1, acc)));
      pos += ratio;
    }
    const drop = Math.max(0, Math.floor(pos) - half);
    hist = buf.slice(drop);
    pos -= drop;
  };
}
