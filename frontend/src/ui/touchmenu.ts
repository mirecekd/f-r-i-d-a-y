// frontend/src/ui/touchmenu.ts
import type * as THREE from "three";
import type { ScenePlayer } from "../scene/player";
import { ContextMenu } from "./ctxmenu";

/** Wires double-tap (frame object) and long-press (context menu) from the 3D view to the player and chat. */
export function wireTouchMenu(
  player: ScenePlayer,
  camera: THREE.PerspectiveCamera,
  target: THREE.Vector3,
  send: (m: { t: string; text: string }) => void,
): void {
  const menu = new ContextMenu();
  const frame = (ids: string[]): void => player.frame(ids, camera, target);
  player.selection.onFrame = (id) => id && frame([id]);
  player.selection.onMenu = (id, x, y) => {
    const label = String(player.entries.get(id)?.obj.label ?? id);
    menu.open(label, x, y, [
      { label: "Zoom to", run: () => frame([id]) },
      { label: "Hide", run: () => player.apply([{ op: "set", id, props: { visible: false } }]) },
      { label: "Delete", run: () => player.apply([{ op: "del", id }]) },
      { label: "Ask Friday", run: () => send({ t: "chat", text: `Rekni mi neco o objektu ${label === id ? id : `${id} (${label})`}` }) },
    ]);
  };
}
