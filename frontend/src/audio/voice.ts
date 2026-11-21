// frontend/src/audio/voice.ts
import type { Net } from "../net";
import { Mic } from "./mic";
import { Player } from "./player";

/** Voice session controller: mic button -> voice_start/voice_stop, audio frames in and out. */
export class Voice {
  private mic = new Mic();
  private player = new Player();
  private on = false;
  private lock: WakeLockSentinel | null = null;
  /** Called with true when a voice session starts and false when it ends. */
  onActive: (on: boolean) => void = () => {};

  constructor(private net: Net, private button: HTMLElement) {
    button.onclick = () => (this.on ? this.stop() : void this.start());
    net.onBinary = (pcm) => this.player.push(pcm);
    net.on((m) => {
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

  /** Output loudness 0..1 for the orb. */
  level(): number {
    return this.player.level();
  }

  private async start(): Promise<void> {
    this.player.init();
    try {
      await this.mic.start((pcm) => this.net.sendBinary(pcm));
    } catch (e) {
      this.mic.stop();
      console.warn("microphone unavailable", e);
      return;
    }
    this.on = true;
    this.button.classList.add("on");
    this.net.send({ t: "voice_start" });
    this.onActive(true);
    navigator.wakeLock?.request("screen").then((l) => (this.on ? (this.lock = l) : void l.release()), () => {});
  }

  private stop(notify = true): void {
    this.on = false;
    this.button.classList.remove("on");
    this.lock?.release().catch(() => {});
    this.lock = null;
    this.mic.stop();
    this.player.flush();
    if (notify) this.net.send({ t: "voice_stop" });
    this.onActive(false);
  }
}
