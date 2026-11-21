// frontend/src/audio/player.ts
const OUT_RATE = 24000; // model output, PCM16 mono

/** Gapless playback of PCM16 chunks on a monotonic playhead, with an analyser for the orb. */
export class Player {
  private ctx?: AudioContext;
  private analyser?: AnalyserNode;
  private playhead = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private samples = new Uint8Array(512);

  /** Creates the context; must be called from a user gesture. */
  init(): void {
    if (this.ctx) return;
    this.ctx = new AudioContext({ sampleRate: OUT_RATE });
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 512;
    this.analyser.connect(this.ctx.destination);
  }

  push(pcm: ArrayBuffer): void {
    if (!this.ctx || !this.analyser) return;
    const ints = new Int16Array(pcm, 0, pcm.byteLength >> 1);
    const buf = this.ctx.createBuffer(1, ints.length, OUT_RATE);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < ints.length; i++) ch[i] = ints[i] / 32768;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.analyser);
    this.playhead = Math.max(this.playhead, this.ctx.currentTime + 0.05);
    src.start(this.playhead);
    this.playhead += buf.duration;
    this.sources.add(src);
    src.onended = () => this.sources.delete(src);
  }

  /** Drops everything queued (barge-in or stop). */
  flush(): void {
    this.sources.forEach((s) => {
      s.onended = null;
      s.stop();
    });
    this.sources.clear();
    this.playhead = 0;
  }

  queued(): number {
    return this.sources.size;
  }

  /** Output loudness 0..1 (RMS of the analyser), for orb.level. */
  level(): number {
    if (!this.analyser || this.sources.size === 0) return 0;
    this.analyser.getByteTimeDomainData(this.samples);
    let sum = 0;
    for (const v of this.samples) sum += ((v - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / this.samples.length) * 4);
  }
}
