// frontend/tests/workshop_page/main.ts
import * as THREE from "three";
import { Net } from "../../src/net";
import { Deck } from "../../src/ui/deck";
import { Workshop } from "../../src/ui/workshop";

const net = new Net();
const camera = new THREE.PerspectiveCamera(50, 1.6, 0.1, 200);
const calls: { glide: unknown[]; asked: string[]; focused: string[] } = { glide: [], asked: [], focused: [] };
const workshop = new Workshop(net, {
  pose: () => ({ pos: [0, 1.2, 9], look: [0, 0, 0] }),
  glide: (pos, look) => calls.glide.push({ pos, look }),
  snapshot: (width) => {
    const c = document.createElement("canvas");
    c.width = width; c.height = Math.round(width / 2);
    const g = c.getContext("2d")!;
    for (let i = 0; i < 400; i++) { g.fillStyle = `hsl(${(i * 37) % 360},70%,50%)`; g.fillRect((i * 13) % c.width, (i * 7) % c.height, 30, 30); }
    return c;
  },
  focus: (id) => calls.focused.push(id),
  selectedWorkshop: () => null,
  ask: (text) => { calls.asked.push(text); net.send({ t: "chat", text }); },
});
new Deck(net, document.getElementById("deckbtn")!, document.getElementById("stage")!, camera, (text) => net.send({ t: "chat", text }), () => workshop.isOpen());
(window as any).__ws = { calls, emit: (m: { t: string }) => net.emit(m) };
net.connect();
