// frontend/src/ui/ctxmenu.ts

export interface MenuAction {
  label: string;
  run: () => void;
}

const MIN_TARGET_PX = 44;

/** Small popup menu for a long-pressed object: big touch targets, closes on outside tap or Escape. */
export class ContextMenu {
  private el = document.createElement("div");

  constructor() {
    this.el.id = "ctxmenu";
    this.el.hidden = true;
    document.body.append(this.el);
    addEventListener("pointerdown", (e) => {
      if (!this.el.hidden && !this.el.contains(e.target as Node)) this.close();
    }, true);
    addEventListener("keydown", (e) => e.key === "Escape" && this.close());
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(title: string, x: number, y: number, actions: MenuAction[]): void {
    this.el.replaceChildren();
    const h = document.createElement("div");
    h.className = "ctx-title";
    h.textContent = title;
    this.el.append(h);
    for (const a of actions) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = a.label;
      b.style.minHeight = `${MIN_TARGET_PX}px`;
      b.onclick = () => {
        this.close();
        a.run();
      };
      this.el.append(b);
    }
    this.el.hidden = false;
    const w = this.el.offsetWidth;
    const hh = this.el.offsetHeight;
    this.el.style.left = `${Math.max(8, Math.min(x - w / 2, innerWidth - w - 8))}px`;
    this.el.style.top = `${Math.max(8, Math.min(y + 12, innerHeight - hh - 8))}px`;
  }

  close(): void {
    this.el.hidden = true;
  }
}
