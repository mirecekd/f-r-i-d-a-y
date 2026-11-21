// frontend/src/ui/entity_menu.ts
import type { ScenePlayer } from "../scene/player";
import { isEntityRef } from "../scene/entity_logic";
import type { MenuAction } from "./ctxmenu";

export type Send = (m: { t: string; [k: string]: unknown }) => void;

/** Entity behaviour on top of the object menu: open card on double tap, link mode, remove from the deck. */
export class EntityActions {
  private linkFrom: string | null = null;

  constructor(private player: ScenePlayer, private send: Send, private notify: (text: string) => void) {}

  isEntity(id: string): boolean {
    const o = this.player.entries.get(id)?.obj;
    return !!o && isEntityRef(o);
  }

  open(id: string): void {
    this.send({ t: "entity_open", id });
  }

  /** Link mode: the next selected entity is linked to `id`. */
  startLink(id: string): void {
    this.linkFrom = id;
    this.notify("Vyber dalsi polozku, ktera se ma spojit.");
  }

  /** The next selected entity (other than the first) gets linked; returns true when the selection was consumed. */
  consumeSelection(ids: string[]): boolean {
    const from = this.linkFrom;
    if (!from || ids.length !== 1 || ids[0] === from) return false;
    if (!this.isEntity(ids[0])) return false;
    this.linkFrom = null;
    this.send({ t: "entity_link", from, to: ids[0] });
    return true;
  }

  /** Menu entries for an entity; 'Smazat z paluby' removes only the scene object, never the stored item. */
  menu(id: string): MenuAction[] {
    return [
      { label: "Otevrit", run: () => this.open(id) },
      {
        label: "Spojit s...",
        run: () => this.startLink(id),
      },
      { label: "Smazat z paluby", run: () => this.send({ t: "entity_remove", id }) },
    ];
  }
}
