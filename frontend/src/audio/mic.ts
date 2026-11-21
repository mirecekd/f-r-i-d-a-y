// frontend/src/audio/mic.ts
import workletUrl from "./capture-worklet.js?worker&url";

/** Microphone capture: getUserMedia -> AudioWorklet -> 16 kHz PCM16 chunks. */
export class Mic {
  private ctx?: AudioContext;
  private stream?: MediaStream;

  /** Starts capture; must be called from a user gesture. Rejects if the mic is denied. */
  async start(onChunk: (pcm: ArrayBuffer) => void): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: 48000, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule(workletUrl);
    const node = new AudioWorkletNode(this.ctx, "capture", { numberOfOutputs: 0 });
    node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onChunk(e.data);
    this.ctx.createMediaStreamSource(this.stream).connect(node);
  }

  stop(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.stream = this.ctx = undefined;
  }
}
