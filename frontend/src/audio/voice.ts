// frontend/src/audio/voice.ts
import type { Net } from "../net";
import { Mic } from "./mic";
import { Player } from "./player";
import { EchoGate, pcmRms, speakerMode } from "./echogate";

const STORE_KEY = "friday.headphones"; // '1' headphones, '0' speaker, unset = automatic
const CHUNK_MS = 64; // one capture chunk, see capture-worklet.js
const SILENCE = new ArrayBuffer(2048); // 1024 samples of digital silence, keeps the server VAD stream alive

/** Voice session controller: mic button -> voice_start/voice_stop, audio frames in and out. */
export class Voice {
  private mic = new Mic();
  private player = new Player();
  private on = false;
  private gate = new EchoGate();
  private serverSpeaking = false;
  private gateClock = 0;
  private lock: WakeLockSentinel | null = null;
  /** Called with true when a voice session starts and false when it ends. */
  onActive: (on: boolean) => void = () => {};

  constructor(private net: Net, private button: HTMLElement) {
    button.onclick = () => (this.on ? this.stop() : void this.start());
    net.onBinary = (pcm) => this.player.push(pcm);
    this.applyMode();
    net.on((m) => {
      if (m.t === "state") this.serverSpeaking = m.state === "speaking";
      if (m.t === "interrupted") this.player.flush();
      if (m.t === "error" && this.on && String(m.message).startsWith("voice:")) this.stop(false);
    });
    net.onStatus = ((prev) => (up: boolean) => {
      prev(up);
      if (!up && this.on) this.stop(false);
    })(net.onStatus);
  }

  get active(): boolean {
    return this.on;
  }

  /** Audio chunks still queued for playback. */
  get queued(): number {
    return this.player.queued();
  }

  /** STOP: end the session locally (the server is told with `stop`), drop all queued audio. */
  halt(): void {
    if (this.on) this.stop(false);
    this.player.flush();
  }

  /** True when the echo gate is on (speaker mode). */
  get gated(): boolean {
    return this.gate.enabled;
  }

  /** Stored choice: '1' headphones, '0' speaker, null automatic. */
  get headphones(): string | null {
    return localStorage.getItem(STORE_KEY);
  }

  set headphones(v: string | null) {
    if (v === null) localStorage.removeItem(STORE_KEY);
    else localStorage.setItem(STORE_KEY, v);
    this.applyMode();
  }

  /** Resolves the toggle (or touch detection) into the gate state and tells the server the profile for the next session. */
  applyMode(): void {
    const touch = navigator.maxTouchPoints > 0 && /Android|iPhone|iPad|Mobile/.test(navigator.userAgent);
    this.gate.enabled = speakerMode(this.headphones, touch);
    this.net.send({ t: "audio_profile", profile: this.gate.enabled ? "speaker" : "headphones" });
  }

  /** Mic chunk -> server, through the echo gate; gated chunks become digital silence. */
  private sendMic(pcm: ArrayBuffer): void {
    this.gateClock += CHUNK_MS;
    const playing = this.player.playing || this.serverSpeaking;
    const open = this.gate.push(pcmRms(pcm), playing, this.gateClock, CHUNK_MS);
    this.net.sendBinary(open ? pcm : SILENCE);
  }

  /** Output loudness 0..1 for the orb. */
  level(): number {
    return this.player.level();
  }

  private async start(): Promise<void> {
    try {
      await this.player.init();
      await this.mic.start((pcm) => this.sendMic(pcm));
    } catch (e) {
      this.mic.stop();
      console.warn("microphone unavailable", e);
      return;
    }
    this.applyMode();
    this.on = true;
    this.button.classList.add("on");
    this.net.send({ t: "voice_start" });
    this.onActive(true);
    navigator.wakeLock?.request("screen").then((l) => (this.on ? (this.lock = l) : void l.release()), () => {});
  }

  private stop(notify = true): void {
    this.on = false;
    this.serverSpeaking = false;
    this.button.classList.remove("on");
    this.lock?.release().catch(() => {});
    this.lock = null;
    this.mic.stop();
    this.player.flush();
    if (notify) this.net.send({ t: "voice_stop" });
    this.onActive(false);
  }
}
