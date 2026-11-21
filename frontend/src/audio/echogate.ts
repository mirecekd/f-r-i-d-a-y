// frontend/src/audio/echogate.ts
// Half-duplex safety net against Friday hearing herself: while she speaks (and for a short tail) the mic is gated,
// unless the user is clearly louder than the echo learned during playback. Pure logic, no DOM, unit-tested.

export const GATE = {
  tailMs: 350, // gate stays closed this long after playback ends
  minThreshold: 0.12, // barge-in RMS floor (PCM scaled to 0..1)
  floorFactor: 3, // barge-in must exceed this multiple of the learned echo floor
  bargeMs: 200, // loud signal needed for this long to open the gate
  learnMs: 300, // start of each of her turns: everything counts as echo, only the floor is learned
  maxFloor: 0.2, // cap of the learned floor, so moderate speech under the threshold cannot ratchet it up without bound
  holdMs: 600, // once opened, the gate stays open this long after the last loud frame
};

/** RMS (0..1) of a PCM16 chunk. */
export function pcmRms(pcm: ArrayBuffer): number {
  const s = new Int16Array(pcm, 0, pcm.byteLength >> 1);
  if (!s.length) return 0;
  let sum = 0;
  for (let i = 0; i < s.length; i++) sum += (s[i] / 32768) ** 2;
  return Math.sqrt(sum / s.length);
}

/** Speaker mode: the stored toggle ('0' speaker, '1' headphones) wins, otherwise touch devices count as speaker. */
export function speakerMode(stored: string | null, touchMobile: boolean): boolean {
  if (stored === "0") return true;
  if (stored === "1") return false;
  return touchMobile;
}

export class EchoGate {
  enabled = true;
  /** Running loudness of the echo measured while Friday speaks and the gate is closed. */
  floor = 0;
  private lastPlayingAt = -Infinity;
  private turnStart = -Infinity;
  private loudMs = 0;
  private openUntil = -Infinity;

  /** Barge-in threshold for the current echo floor. */
  get threshold(): number {
    return Math.max(GATE.minThreshold, GATE.floorFactor * this.floor);
  }

  /** One mic frame: its RMS, whether Friday is speaking, time in ms and frame length in ms. True = send the audio. */
  push(rms: number, playing: boolean, nowMs: number, frameMs: number): boolean {
    if (!this.enabled) return true;
    if (playing) {
      if (nowMs - this.lastPlayingAt >= GATE.tailMs) this.turnStart = nowMs;
      this.lastPlayingAt = nowMs;
    }
    if (!playing && nowMs - this.lastPlayingAt >= GATE.tailMs) {
      this.loudMs = 0;
      this.openUntil = -Infinity;
      this.floor *= 0.999 ** (frameMs / 20); // forget very slowly: echo loudness is a property of the device
      return true;
    }
    if (rms > this.threshold && nowMs - this.turnStart >= GATE.learnMs) {
      this.loudMs += frameMs;
      if (this.loudMs >= GATE.bargeMs) this.openUntil = nowMs + GATE.holdMs;
    } else {
      this.loudMs = 0;
      this.floor = Math.min(GATE.maxFloor, this.floor + (rms - this.floor) * (rms > this.floor ? 0.3 : 0.05)); // fast attack, slow release
    }
    return nowMs < this.openUntil;
  }
}
