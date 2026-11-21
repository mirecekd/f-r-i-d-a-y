// frontend/src/ui/touchmenu.ts
import type * as THREE from "three";
import type { ScenePlayer } from "../scene/player";
import { ContextMenu } from "./ctxmenu";
import { EntityActions, type Send } from "./entity_menu";

/** Wires double-tap (frame object, or open an entity's card) and long-press (context menu) from the 3D view to the player and chat. */
export function wireTouchMenu(
  player: ScenePlayer,
  camera: THREE.PerspectiveCamera,
  target: THREE.Vector3,
  send: Send,
  notify: (text: string) => void = () => {},
): EntityActions {
  const menu = new ContextMenu();
  const frame = (ids: string[]): void => player.frame(ids, camera, target);
  const entities = new EntityActions(player, send, notify);
  const selected = player.onSelect;
  player.onSelect = (ids) => {
    if (!entities.consumeSelection(ids)) selected(ids);
  };
  // Double tap: an entity opens its readable card; any other object keeps the frame-it behaviour.
  player.selection.onFrame = (id) => id && (entities.isEntity(id) ? entities.open(id) : frame([id]));
  player.selection.onMenu = (id, x, y) => {
    const label = String(player.entries.get(id)?.obj.label ?? id);
    if (entities.isEntity(id)) return menu.open(label, x, y, [{ label: "Zoom to", run: () => frame([id]) }, ...entities.menu(id)]);
    menu.open(label, x, y, [
      { label: "Zoom to", run: () => frame([id]) },
      { label: "Hide", run: () => player.apply([{ op: "set", id, props: { visible: false } }]) },
      { label: "Delete", run: () => player.apply([{ op: "del", id }]) },
      { label: "Ask Friday", run: () => send({ t: "chat", text: `Rekni mi neco o objektu ${label === id ? id : `${id} (${label})`}` }) },
    ]);
  };
  return entities;
}
