// frontend/src/net.ts
export type Msg = { t: string; [k: string]: any };

/** WebSocket with auto-reconnect. Same-origin, so the reverse proxy auth cookies apply. */
export class Net {
  private ws?: WebSocket;
  private handlers: ((m: Msg) => void)[] = [];
  onStatus: (up: boolean) => void = () => {};
  onBinary: (data: ArrayBuffer) => void = () => {};

  on(fn: (m: Msg) => void): void {
    this.handlers.push(fn);
  }

  /** Feed a message to the handlers as if the server sent it (debug hook for headless tests). */
  emit(m: Msg): void {
    this.handlers.forEach((h) => h(m));
  }

  connect(): void {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => this.onStatus(true);
    ws.onmessage = (e) => {
      if (typeof e.data === "string") this.handlers.forEach((h) => h(JSON.parse(e.data)));
      else this.onBinary(e.data);
    };
    ws.onclose = () => {
      this.onStatus(false);
      setTimeout(() => this.connect(), 1500);
    };
  }

  /** False when the socket is not open and the message was dropped. */
  send(m: Msg): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(m));
    return true;
  }

  sendBinary(data: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(data);
  }
}
