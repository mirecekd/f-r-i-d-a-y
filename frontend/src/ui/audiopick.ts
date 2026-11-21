// frontend/src/ui/audiopick.ts
import type { Voice } from "../audio/voice";
import { el } from "../views/dom";
import "./audiopick.css";

const CHOICES: { value: string | null; label: string }[] = [
  { value: "1", label: "Sluchatka (plna duplex, bez omezeni)" },
  { value: "0", label: "Reproduktor (zabrani ozvene)" },
  { value: null, label: "Automaticky" },
];

/** Settings section "Zvuk": headphones / speaker / automatic. Speaker mode turns the echo gate on. */
export class AudioPick {
  private buttons: HTMLButtonElement[] = [];
  private note = el("p", "st-note ap-note");

  constructor(host: HTMLElement, private voice: Voice) {
    const group = el("div", "ap-group");
    group.setAttribute("role", "radiogroup");
    group.setAttribute("aria-label", "Zvuk");
    for (const c of CHOICES) {
      const b = el("button", "mp-btn ap-opt", c.label);
      b.type = "button";
      b.setAttribute("role", "radio");
      b.onclick = () => {
        voice.headphones = c.value;
        this.refresh();
      };
      this.buttons.push(b);
      group.append(b);
    }
    host.append(group, this.note);
    this.refresh();
  }

  private refresh(): void {
    const stored = this.voice.headphones;
    CHOICES.forEach((c, i) => {
      const on = c.value === stored;
      this.buttons[i].classList.toggle("on", on);
      this.buttons[i].setAttribute("aria-checked", String(on));
    });
    this.note.textContent = this.voice.gated
      ? "Mikrofon se behem rece Friday tlumi, preruseni je mozne hlasitou rec."
      : "Mikrofon je otevreny stale.";
  }
}
