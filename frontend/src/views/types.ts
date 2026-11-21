// frontend/src/views/types.ts
export interface ViewMsg {
  id: string;
  kind: string;
  title?: string;
  data: any;
}

/** Optional teardown returned by a renderer (observers, listeners). `update` lets a new view of the same kind refresh the open panel in place. */
export type Cleanup = (() => void) & { update?: (data: any) => void };

/** Fills `body` with the view. May be async (diagram). Must never use innerHTML with model text. */
export type Renderer = (body: HTMLElement, data: any) => void | Cleanup | Promise<void | Cleanup>;

export interface ViewKind {
  render: Renderer;
  /** Default panel size in px: [width, height]. */
  size: [number, number];
}
