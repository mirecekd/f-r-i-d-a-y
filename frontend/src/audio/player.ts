// frontend/src/audio/player.ts
const OUT_RATE = 24000; // model output, PCM16 mono

/** Gapless playback of PCM16 chunks on a monotonic playhead, with an analyser for the orb. */
export class Player {
  private ctx?: AudioContext;
  private el?: HTMLAudioElement;
  private analyser?: AnalyserNode;
  private playhead = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private samples = new Uint8Array(512);

  /**
   * Creates the context; must be called from a user gesture. The output goes through a MediaStream into a hidden
   * <audio> element instead of ctx.destination: browsers use media elements as the echo canceller's render
   * reference, plain Web Audio output leaks back into the microphone on phones. Resolves once playback started.
   */
  async init(): Promise<void> {
    if (this.ctx) return void (await this.el?.play().catch(() => {}));
    const ctx = (this.ctx = new AudioContext({ sampleRate: OUT_RATE, latencyHint: "interactive" }));
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 512;
    const dest = ctx.createMediaStreamDestination();
    this.analyser.connect(dest);
    const el = (this.el = document.createElement("audio"));
    el.hidden = true;
    el.autoplay = true;
    el.setAttribute("playsinline", "");
    el.srcObject = dest.stream;
    document.body.append(el);
    const started = el.play().catch((e) => console.warn("audio element play() failed", e));
    await Promise.race([Promise.all([ctx.resume(), started]), new Promise((r) => setTimeout(r, 1500))]); // never hang the mic start
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

  /** True while chunks are scheduled or sounding. */
  get playing(): boolean {
    return this.sources.size > 0;
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
