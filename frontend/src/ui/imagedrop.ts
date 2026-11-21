// frontend/src/ui/imagedrop.ts
import "./imagedrop.css";
import type { Msg, Net } from "../net";
import { fileCardActions } from "../views/file_card";
import { imageCardActions } from "../views/image_card";
import type { Chat } from "./chat";
import { newId, prepare, toBase64, validate, validateFile } from "./imageprep";

/** Files (images and anything else) enter through the chat: window drag and drop, paste in the chat input, and the paperclip button. */
export class ImageDrop {
  private overlay = document.createElement("div");
  private depth = 0;

  constructor(private net: Net, private chat: Chat) {
    this.overlay.id = "dropveil";
    this.overlay.textContent = "Pust soubor";
    document.body.append(this.overlay);
    fileCardActions.chat = (text) => {
      chat.message("user", text);
      net.send({ t: "chat", text });
    };
    imageCardActions.toScene = (id) => net.send({ t: "image_to_scene", id });
    net.on((m) => this.onMessage(m));

    addEventListener("dragenter", (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      this.depth++;
      this.overlay.classList.add("show");
    });
    addEventListener("dragover", (e) => hasFiles(e) && e.preventDefault());
    addEventListener("dragleave", () => {
      if (this.depth > 0 && --this.depth <= 0) this.hide();
    });
    addEventListener("drop", (e) => {
      const files = [...(e.dataTransfer?.files ?? [])];
      this.hide();
      if (!files.length) return;
      e.preventDefault();
      files.forEach((f) => void this.send(f));
    });
    document.getElementById("input")!.addEventListener("paste", (e) => {
      const files = [...(e.clipboardData?.files ?? [])];
      if (!files.length) return;
      e.preventDefault();
      files.forEach((f) => void this.send(f));
    });
    const picker = document.getElementById("attachfile") as HTMLInputElement;
    picker.removeAttribute("accept"); // any file may be attached
    picker.multiple = true;
    document.getElementById("attach")!.onclick = () => picker.click();
    picker.onchange = () => {
      [...(picker.files ?? [])].forEach((f) => void this.send(f));
      picker.value = "";
    };
  }

  private hide(): void {
    this.depth = 0;
    this.overlay.classList.remove("show");
  }

  /** Validate, show the bubble at once, then send the file (images are possibly downscaled first). */
  async send(file: File): Promise<void> {
    if (!file.type.startsWith("image/")) return this.sendFile(file);
    const id = newId();
    this.chat.open();
    const bad = validate(file);
    if (bad) return this.chat.message("error", bad);
    const thumb = URL.createObjectURL(file);
    this.chat.imageStart({ k: "img", id, name: file.name || "obrazek", state: "sending" }, thumb);
    try {
      const prep = await prepare(file);
      const data_b64 = await toBase64(prep.blob);
      if (!this.net.send({ t: "image_upload", id, name: prep.name, mime: prep.mime, data_b64 })) {
        return this.chat.images.update(id, { state: "failed", error: "Neni spojeni se serverem." });
      }
      if (prep.downscaled) {
        this.chat.message("assistant", "Velka fotka byla zmensena na 2400 px a znovu zakodovana; polohova data (GPS) a dalsi EXIF se tim ztratily.");
      }
    } catch (e) {
      return this.chat.images.update(id, { state: "failed", error: `Obrazek nelze zpracovat: ${(e as Error).message}` });
    }
    this.chat.images.update(id, { state: "sending" });
  }

  /** A non-image file: chip bubble now, `file_upload` with the raw bytes as base64, the server answers `file_ready`. */
  private async sendFile(file: File): Promise<void> {
    const id = newId();
    this.chat.open();
    const bad = validateFile(file);
    if (bad) return this.chat.message("error", bad);
    this.chat.fileStart({ k: "img", id, name: file.name || "soubor", state: "sending", file: { kind: "file", size: file.size } });
    try {
      const data_b64 = await toBase64(file);
      if (!this.net.send({ t: "file_upload", id, name: file.name || "soubor", mime: file.type, data_b64 })) {
        this.chat.images.update(id, { state: "failed", error: "Neni spojeni se serverem." });
      }
    } catch (e) {
      this.chat.images.update(id, { state: "failed", error: `Soubor nelze precist: ${(e as Error).message}` });
    }
  }

  private onMessage(m: Msg): void {
    if (m.t === "file_ready" && m.client_id) {
      this.chat.images.update(m.client_id, { state: "ready", url: m.url, file: { kind: m.kind, size: m.size } });
    } else if (m.t === "image_ready" && m.client_id) {
      this.chat.images.update(m.client_id, { state: "analysing", url: m.url, w: m.w, h: m.h, exif: m.exif });
    } else if (m.t === "view" && m.kind === "image_card") {
      this.chat.images.settle(m.data?.url);
    } else if (m.t === "error" && m.id) {
      this.chat.images.update(m.id, { state: "failed", error: String(m.message) });
    } else if (m.t === "error" && String(m.message).startsWith("image analysis failed")) {
      this.chat.images.settle();
    }
  }
}

function hasFiles(e: DragEvent): boolean {
  return !!e.dataTransfer?.types.includes("Files");
}
