// frontend/src/core/params.ts

/** Render-cost overrides read from the URL; defaults keep production visuals unchanged. */
export interface RenderParams {
  particles: number; // orb particle count
  pixelRatio: number; // max device pixel ratio
  bloom: boolean;
  offline: boolean; // do not open the WebSocket (tests without backend)
  fixedStep: number; // 0 = real time; >0 = fixed dt per frame (deterministic test shots)
}

/** ?lowfx (implies offline) cuts cost for software GL; ?particles=N, ?px=R, ?bloom=0 and ?step=S override single values. */
export function readParams(search = location.search): RenderParams {
  const q = new URLSearchParams(search);
  const low = q.has("lowfx");
  const num = (k: string, d: number): number => {
    const v = Number(q.get(k));
    return q.has(k) && Number.isFinite(v) && v >= 0 ? v : d;
  };
  return {
    particles: Math.max(100, Math.floor(num("particles", low ? 4000 : 24000))),
    pixelRatio: Math.max(0.25, num("px", low ? 1 : 2)),
    bloom: q.get("bloom") ? q.get("bloom") !== "0" : true,
    offline: q.has("offline") || low,
    fixedStep: num("step", 0),
  };
}

export const params = readParams();
