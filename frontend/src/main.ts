// frontend/src/main.ts
import * as THREE from "three";
import "./style.css";
import { Stage } from "./core/stage";
import type { OrbState } from "./core/orblook";
import { OrbMini } from "./ui/orbmini";
import { ScenePlayer } from "./scene/player";
import { Net } from "./net";
import { Chat } from "./ui/chat";
import { Voice } from "./audio/voice";
import { params } from "./core/params";
import { views } from "./views/host";
import { glideStep } from "./core/glide";
import { wireTouchMenu } from "./ui/touchmenu";
import { Models } from "./ui/models";
import { Settings } from "./ui/settings";
import { Confirm } from "./ui/confirm";
import { Capture } from "./ui/capture";
import { ImageDrop } from "./ui/imagedrop";
import { ZoomBox } from "./ui/zoombox";
import { demoGraph } from "./views/memory_demo";

const stage = new Stage(document.getElementById("stage") as HTMLCanvasElement);
// The orb lives in its own small canvas (own renderer and loop), not in the 3D scene.
const miniOrb = new OrbMini(document.getElementById("orbmini") as HTMLCanvasElement);
const orb = miniOrb.orb;
if (location.search.includes("noorb")) miniOrb.hide(); // ?noorb: no orb (headless tests)

// Camera moves requested by the model glide instead of jumping.
let camGoal: { pos: THREE.Vector3; look: THREE.Vector3 } | null = null;
const player = new ScenePlayer((pos, look) => (camGoal = { pos, look }));
stage.scene.add(player.root);
player.attachPicking(stage.renderer.domElement, stage.camera);
stage.onTick((_dt, t) => player.tick(t));
stage.onTick((dt) => {
  if (!camGoal) return;
  if (!glideStep(camGoal, stage.camera, stage.controls.target, dt)) camGoal = null;
});

new ZoomBox(stage, player, (pos, look) => (camGoal = { pos, look }));

const net = new Net();
player.onSelect = (ids) => net.send({ t: "select", ids });
wireTouchMenu(player, stage.camera, stage.controls.target, (m) => net.send(m));
const chat = new Chat(net);
new ImageDrop(net, chat);
const settings = new Settings(net, document.getElementById("settingsbtn")!);
new Models(net, settings.section("Modely"));
new Confirm(net);
const voice = new Voice(net, document.getElementById("mic")!);
new Capture(net, voice);
document.getElementById("membtn")!.onclick = () => net.send({ t: "show_memory_graph" });
stage.onTick(() => (orb.level = voice.level()));
const setState = (s: OrbState): void => miniOrb.setState(s);

net.onStatus = (up) => miniOrb.setOffline(!up);

net.on((m) => {
  switch (m.t) {
    case "state": return setState(m.state);
    case "scene": return player.apply(m.ops);
    case "scene_full": return player.full(m.objects);
    case "chat": return chat.message(m.role, m.text, m.id);
    case "chat_delta": return chat.delta(m.id, m.text);
    case "transcript": return chat.transcript(m.role, m.text, m.final);
    case "tool": return chat.tool(m.id, m.name, m.status, m.ms);
    case "view": return views.show(m as any);
    case "view_close": return views.close(m.id);
    case "error": return m.id && chat.images.has(m.id) ? undefined : chat.message("error", m.message);
  }
});
if (!params.offline) net.connect();

// Debug hook for headless screenshot tests: window.__friday.state("speaking")
(window as any).__friday = { state: setState, offline: (v: boolean) => miniOrb.setOffline(v), level: (v: number) => (orb.level = v), player, views, camera: stage.camera, voiceActive: (on: boolean) => voice.onActive(on), send: (m: { t: string }) => net.send(m), emit: (m: { t: string }) => net.emit(m), chat: (r: string, t: string) => chat.message(r, t), tool: (id: string, n: string, s: string, ms?: number) => chat.tool(id, n, s, ms), memoryDemo: (n = 150) => views.show({ id: "memdemo", kind: "memory_graph", title: "Memory orbs (demo)", data: demoGraph(n) }) };
