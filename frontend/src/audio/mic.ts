// frontend/src/audio/mic.ts
import workletUrl from "./capture-worklet.js?worker&url";

/** Microphone capture: getUserMedia -> AudioWorklet -> 16 kHz PCM16 chunks. */
export class Mic {
  private ctx?: AudioContext;
  private stream?: MediaStream;
  /** Settings the browser actually applied (echoCancellation etc.); empty before start. */
  applied: MediaTrackSettings = {};

  /** Richest constraints first; browsers that reject an unknown or unsatisfiable one get the basic set. */
  private async open(): Promise<MediaStream> {
    const basic = { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true };
    const rich = {
      ...basic,
      echoCancellation: { ideal: true },
      latency: 0,
      voiceIsolation: true,
      googEchoCancellation: true,
      googNoiseSuppression: true,
    };
    try {
      return await navigator.mediaDevices.getUserMedia({ audio: rich as MediaTrackConstraints, video: false });
    } catch (e) {
      if (!(e instanceof OverconstrainedError || (e instanceof DOMException && e.name === "TypeError"))) throw e;
      console.warn("rich audio constraints rejected, using the basic set", e);
      return navigator.mediaDevices.getUserMedia({ audio: basic, video: false });
    }
  }

  /** Starts capture; must be called from a user gesture. Rejects if the mic is denied. */
  async start(onChunk: (pcm: ArrayBuffer) => void): Promise<void> {
    this.stream = await this.open();
    this.applied = this.stream.getAudioTracks()[0]?.getSettings() ?? {};
    console.info("mic settings", { echoCancellation: this.applied.echoCancellation, noiseSuppression: this.applied.noiseSuppression, autoGainControl: this.applied.autoGainControl });
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
