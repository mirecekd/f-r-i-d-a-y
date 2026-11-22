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
import { AssetCredits } from "./ui/credits";
import { Settings } from "./ui/settings";
import { VoicePick } from "./ui/voicepick";
import { ThinkingPick } from "./ui/thinkingpick";
import { AudioPick } from "./ui/audiopick";
import { Confirm } from "./ui/confirm";
import { Capture } from "./ui/capture";
import { ImageDrop } from "./ui/imagedrop";
import { NewChat } from "./ui/newchat";
import { ZoomBox } from "./ui/zoombox";
import { StopButton } from "./ui/stopbutton";
import { GestureButton } from "./ui/gesturebtn";
import { EntityBar } from "./ui/entitybar";
import { Deck } from "./ui/deck";
import { Workshop } from "./ui/workshop";
import { DropNotice } from "./ui/dropnotice";
import { HudState } from "./ui/hudstate";
import { demoGraph, demoSearchGraph } from "./views/memory_demo";

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

const zoom = new ZoomBox(stage, player, (pos, look) => (camGoal = { pos, look }));

const net = new Net();
player.onSelect = (ids) => net.send({ t: "select", ids });
const entities = wireTouchMenu(player, stage.camera, stage.controls.target, (m) => net.send(m), (text) => chat.message("assistant", text));
const chat = new Chat(net);
const askChat = (text: string): void => { chat.message("user", text); net.send({ t: "chat", text }); };
const workshop = new Workshop(net, {
  pose: () => ({ pos: stage.camera.position.toArray(), look: stage.controls.target.toArray() }),
  glide: (pos, look) => (camGoal = { pos: new THREE.Vector3(...pos), look: new THREE.Vector3(...look) }),
  snapshot: (width) => stage.snapshot(width),
  focus: (id) => player.frame([id], stage.camera, stage.controls.target),
  selectedWorkshop: () => { const o = player.entries.get(player.selection.ids[0] ?? "")?.obj; return player.selection.ids.length === 1 && (o?.ref as { type?: string; id?: string } | undefined)?.type === "workshop" ? String((o!.ref as { id: string }).id) : null; },
  ask: (text) => askChat(text),
});
const entityBar = new EntityBar(player, stage.camera, entities, (m) => net.send(m), askChat);
stage.onTick(() => entityBar.update());
const dropNotice = new DropNotice(net, player, (ids) => player.frame(ids, stage.camera, stage.controls.target), askChat);
new Deck(net, document.getElementById("deckbtn")!, stage.renderer.domElement, stage.camera, askChat, () => workshop.isOpen());
new ImageDrop(net, chat);
new HudState(net);
new NewChat(net, chat);
const settings = new Settings(net, document.getElementById("settingsbtn")!);
new Models(net, settings.section("Modely"));
new VoicePick(net, settings.section("Hlas a jazyk"));
new AssetCredits(net, settings.section("Zdroje modelu"));
new ThinkingPick(net, settings.section("Modely"));
const confirm = new Confirm(net);
const voice = new Voice(net, document.getElementById("mic")!);
new AudioPick(settings.section("Zvuk"), voice);
const capture = new Capture(net, voice);
new StopButton(net, document.getElementById("stopbtn")!, { voice, capture, zoom, confirm });
new GestureButton({ camera: stage.camera, controls: stage.controls, player, views, net }, settings.section("Gesta rukou"));
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
    case "view": return dropNotice.keepsView(m) ? views.show(m as any) : undefined;
    case "view_close": return views.close(m.id);
    case "error": return m.id && chat.images.has(m.id) ? undefined : chat.message("error", m.message);
  }
});
if (!params.offline) net.connect();

// Debug hook for headless screenshot tests: window.__friday.state("speaking")
(window as any).__friday = { state: setState, offline: (v: boolean) => miniOrb.setOffline(v), level: (v: number) => (orb.level = v), player, views, voice, camera: stage.camera, voiceActive: (on: boolean) => voice.onActive(on), send: (m: { t: string }) => net.send(m), emit: (m: { t: string }) => net.emit(m), chat: (r: string, t: string) => chat.message(r, t), tool: (id: string, n: string, s: string, ms?: number) => chat.tool(id, n, s, ms), memorySearchDemo: async (query = "nginx") => { views.show({ id: "memdemo", kind: "memory_graph", title: "Memory orbs (demo)", data: demoGraph(150) }); for (let i = 0; i < 60 && !document.querySelector(".mg canvas"); i++) await new Promise((r) => setTimeout(r, 100)); views.show({ id: "memdemo2", kind: "memory_graph", title: "Memory orbs (demo)", data: demoSearchGraph(query) }); }, memoryDemo: (n = 150) => views.show({ id: "memdemo", kind: "memory_graph", title: "Memory orbs (demo)", data: demoGraph(n) }) };
