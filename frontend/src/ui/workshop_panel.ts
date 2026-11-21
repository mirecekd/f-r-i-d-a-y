// frontend/src/ui/workshop_panel.ts
import { glyphCanvas } from "../core/glyphs";
import { glyphForEntity } from "../scene/entity_logic";
import { el } from "../views/dom";
import { formatValue, HINT, parseField, sameParamShape, showHint, type WorkshopState, type WsParam } from "./workshop_logic";

export interface PanelActions {
  /** A slider or field changed (the caller throttles). */
  param(name: string, value: number): void;
  /** The change is final (slider released, field confirmed): send the held value now. */
  commit(name: string): void;
  undo(): void;
  redo(): void;
  leave(): void;
  ask(text: string): void;
  focus(entityId: string): void;
  removeSource(title: string): void;
}

interface Row { param: WsParam; slider: HTMLInputElement; field: HTMLInputElement }

function button(text: string, cls: string, title: string, run: () => void): HTMLButtonElement {
  const b = el("button", cls, text);
  b.type = "button";
  b.title = title;
  b.onclick = run;
  return b;
}

/** The glass side panel of an open workshop: parameters, sources, undo / redo, leave and a question field. Rebuilds only when the sliders change shape. */
export class WorkshopPanel {
  readonly root = el("aside", "ws-panel");
  private title = el("span", "ws-title");
  private body = el("div", "ws-body");
  private notes = el("div", "ws-notes");
  private params = el("div", "ws-params");
  private sources = el("div", "ws-sources");
  private hint = el("div", "ws-hint", HINT);
  private rows = new Map<string, Row>();
  private shown: WsParam[] = [];
  private collapse: HTMLButtonElement;

  constructor(private act: PanelActions) {
    this.root.hidden = true;
    this.root.setAttribute("aria-label", "Dilna");
    this.collapse = button("-", "ws-collapse", "Sbalit nebo rozbalit panel", () => this.setCollapsed(!this.root.classList.contains("collapsed")));
    this.collapse.setAttribute("aria-expanded", "true");
    const head = el("div", "ws-head");
    head.append(el("span", "ws-name", "DILNA"), this.title, this.collapse);
    const acts = el("div", "ws-acts");
    acts.append(
      button("Zpet", "ws-undo", "Vratit posledni zmenu", () => act.undo()),
      button("Znovu", "ws-redo", "Provest vracenou zmenu znovu", () => act.redo()),
      button("Odejit z dilny", "ws-leave", "Zpet na plochu (Esc)", () => act.leave()),
    );
    this.body.append(this.notes, el("div", "ws-h", "PARAMETRY"), this.params, el("div", "ws-h", "ZDROJE"), this.sources, this.hint, acts, this.askForm());
    this.root.append(head, this.body);
    document.body.append(this.root);
  }

  private askForm(): HTMLFormElement {
    const form = el("form", "ws-ask");
    const input = el("input", "ws-ask-input");
    input.placeholder = "Zeptat se...";
    input.setAttribute("aria-label", "Zeptat se na dilnu");
    input.autocomplete = "off";
    const go = el("button", "ws-ask-go", "Zeptat se");
    go.type = "submit";
    form.append(input, go);
    form.onsubmit = (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      this.act.ask(text);
    };
    return form;
  }

  setCollapsed(on: boolean): void {
    this.root.classList.toggle("collapsed", on);
    this.collapse.setAttribute("aria-expanded", String(!on));
    this.collapse.textContent = on ? "+" : "-";
  }

  update(s: WorkshopState): void {
    this.root.hidden = !s.open;
    if (!s.open) return;
    this.title.textContent = s.title || "Nova dilna";
    this.notes.replaceChildren(...s.notes.map((n) => el("div", "ws-note", n)));
    if (sameParamShape(this.shown, s.params)) for (const p of s.params) this.setValue(p);
    else this.buildParams(s.params);
    this.shown = s.params;
    this.sources.replaceChildren(...s.sources.map((src) => this.sourceRow(src.entity_id, src.title, src.kind)));
    this.hint.hidden = !showHint(s);
  }

  private setValue(p: WsParam): void {
    const row = this.rows.get(p.name);
    if (!row || document.activeElement === row.slider || document.activeElement === row.field) return;
    row.slider.value = String(p.value);
    row.field.value = formatValue(p.value, p.step);
  }

  private buildParams(list: WsParam[]): void {
    this.rows.clear();
    this.params.replaceChildren(...list.map((p) => this.paramRow(p)));
  }

  private paramRow(p: WsParam): HTMLElement {
    const row = el("div", "ws-param");
    row.dataset.name = p.name;
    const slider = el("input", "ws-slider");
    slider.type = "range";
    slider.min = String(p.min); slider.max = String(p.max); slider.step = String(p.step); slider.value = String(p.value);
    slider.setAttribute("aria-label", p.label);
    const field = el("input", "ws-field");
    field.type = "text";
    field.inputMode = "decimal";
    field.value = formatValue(p.value, p.step);
    field.setAttribute("aria-label", `${p.label} - hodnota`);
    slider.oninput = () => { field.value = formatValue(Number(slider.value), p.step); this.act.param(p.name, Number(slider.value)); };
    slider.onchange = () => this.act.commit(p.name);
    field.onkeydown = (e) => e.stopPropagation();
    field.onchange = () => {
      const v = parseField(field.value, p);
      if (v === null) { field.value = formatValue(Number(slider.value), p.step); return; }
      slider.value = String(v);
      field.value = formatValue(v, p.step);
      this.act.param(p.name, v);
      this.act.commit(p.name);
    };
    row.append(el("label", "ws-label", p.unit ? `${p.label} (${p.unit})` : p.label), slider, field);
    this.rows.set(p.name, { param: p, slider, field });
    return row;
  }

  private sourceRow(entityId: string, title: string, kind: string): HTMLElement {
    const row = el("div", "ws-source");
    const pick = button("", "ws-src-pick", `Ukazat ${title}`, () => this.act.focus(entityId));
    pick.append(glyphCanvas(glyphForEntity(kind, title), "#4fd8ff", 32), el("span", "ws-src-title", title));
    row.append(pick, button("x", "ws-src-x", `Odebrat ${title} z dilny`, () => this.act.removeSource(title)));
    return row;
  }
}
