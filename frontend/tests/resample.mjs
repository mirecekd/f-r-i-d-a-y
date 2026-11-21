// frontend/tests/resample.mjs
// Aliasing check for the mic downsampler: a 6 kHz tone must survive, a 20 kHz tone (above the 16 kHz target's
// Nyquist) must be strongly attenuated versus the old box-averaging method. Run: node tests/resample.mjs
import { makeResampler } from "../src/audio/resample.js";

const OUT = 16000;

function sine(freq, inRate, seconds) {
  const x = new Float32Array(Math.floor(inRate * seconds));
  for (let i = 0; i < x.length; i++) x[i] = 0.5 * Math.sin((2 * Math.PI * freq * i) / inRate);
  return x;
}

function boxAverage(x, inRate) {
  const ratio = inRate / OUT;
  const out = [];
  let pos = 0, sum = 0, count = 0;
  for (const v of x) {
    sum += v; count++; pos += 1;
    if (pos >= ratio) { pos -= ratio; out.push(sum / count); sum = 0; count = 0; }
  }
  return out;
}

function firResample(x, inRate) {
  const out = [];
  const push = makeResampler(inRate, OUT);
  for (let i = 0; i < x.length; i += 128) push(x.subarray(i, i + 128), (v) => out.push(v));
  return out;
}

const rms = (a) => Math.sqrt(a.reduce((s, v) => s + v * v, 0) / Math.max(1, a.length));
const settled = (a) => a.slice(Math.floor(a.length * 0.1)); // drop the filter start-up
const db = (r) => 20 * Math.log10(Math.max(r, 1e-9));

let failed = false;
for (const inRate of [48000, 44100]) {
  const pass = (f) => rms(settled(firResample(sine(f, inRate, 1), inRate)));
  const oldAlias = (f) => rms(settled(boxAverage(sine(f, inRate, 1), inRate)));
  const ref = rms(sine(6000, inRate, 1));
  const keep = pass(6000) / ref;
  const aliasNew = pass(20000), aliasOld = oldAlias(20000);
  const gain = db(aliasOld / Math.max(aliasNew, 1e-9));
  console.log(
    `${inRate} Hz: 6 kHz kept ${db(keep).toFixed(1)} dB | 20 kHz alias old ${db(aliasOld / ref).toFixed(1)} dB, ` +
      `new ${db(aliasNew / ref).toFixed(1)} dB, improvement ${gain.toFixed(1)} dB`,
  );
  if (keep < 0.9 || keep > 1.1) { console.log("FAIL: passband not flat"); failed = true; }
  if (gain < 20) { console.log("FAIL: alias not attenuated enough"); failed = true; }
}
process.exit(failed ? 1 : 0);
