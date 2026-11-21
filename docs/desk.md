# Desk interactions (entities and the Deck)

The desk is the 3D scene. Files, photos and saved items appear on it as entity tiles; the Deck is the browsable list of everything stored.

## After a drop
A dropped or attached file goes to the desk first. When the upload answer (`file_ready` / `image_ready`, id `X`) and the scene object whose
`ref.id` is `X` have both arrived, the client selects the new entity once, glides the camera to it and shows a toast
"Soubor je na plose: <name>" with `Otevrit` (`entity_open`) and `Zeptat se` (chat text `Co je to za soubor <name>?`). The toast disappears
after 8 s. The automatic `file_card` / `image_card` view that follows such an upload (within 2.5 s) is not shown; open it with `Otevrit`.
You can also just ask by name in the chat ("co je soubor architect.webp"); the backend resolves the name.

## Action bar
With exactly one entity selected, a bar follows it on screen (above its top edge, below when there is no room, clamped to the viewport):
`Zavrit x` (`entity_remove`: leaves the desk only, the stored item stays in the Deck), `Otevrit`, `Spojit` (link mode), `Zeptat se`.
Keys: Delete / Backspace remove, Esc deselects, Enter opens. They are ignored while typing in a field or while the Deck is open.
Targets are at least 44 px. Maths: `frontend/src/ui/entitybar_logic.ts`.

## Deck window
Dock button or key D. Sends `deck_list {type?, q?, offset?}` and renders the `deck` answer as tiles: thumbnail or glyph, title, subtitle,
relative time, tag chips, pin star, provenance line "vznikl z: N polozek" (opens the first parent). Type filter chips with counts, debounced
search (250 ms), sort (newest / pinned first / name), `Nacist dalsi` paging, arrow / Home / End keys between tiles, Enter opens.
Tile actions: `Na plochu` (`deck_place`), context button with Pin, Stitky... (`deck_tag`), Zapomenout (two clicks within 4 s, `deck_forget`).
`deck_changed` while the window is open refreshes the list.

Drag a tile by its thumbnail: a ghost follows the pointer (mouse or touch). Dropping on the 3D canvas sends `deck_place {id, pos}` with the
point where the camera ray meets the desk plane `y = 1.2` (`dropPositionOnDesk`; a drop that misses the desk sends no `pos`). Dropping on the
chat panel sends the chat text `Pouzij <title> (<id>)`.

## Workshop
A Workshop (Dilna) is a place in the same 3D scene, far from the desk (the server gives each one an origin); the browser only moves the camera
and shows a side panel. Enter with the key W (opens the selected workshop tile, else the last visited one, else creates a new one), by
double-clicking a workshop tile, by `Otevrit dilnu` on a Deck tile of type `workshop`, or with `Nova dilna` in the Deck window (`workshop_new`).
Leave with `Odejit z dilny`, W or Esc (Esc steps aside while a dropdown, dialog, chat or the Deck is open); the camera glides there and back.

Panel (docked right, bottom left on narrow screens, collapsible, 44 px targets): the title, the server's warnings, one slider plus numeric field per
parameter (sent as `workshop_param`, at most 12 per second per parameter, the final value at once on release), the sources (click focuses the entity
in 3D, `x` asks the model `Odeber zdroj <title> z dilny`), `Zpet` / `Znovu` (`workshop_undo` / `workshop_redo`) and a question field (chat).
An empty workshop shows `Hod sem obrazek nebo soubor z Decku a rekni, co mam postavit.` Dragging a Deck tile onto the canvas while a workshop is
open sends the chat text `Pridej do dilny <title> (<id>)` instead of `deck_place`. The entity bar's `Zavrit x` is hidden inside a workshop.

Snapshots: on `workshop_snapshot_request` the browser renders one frame from the current camera, scales it to at most 1024 px (or the requested
width), encodes a JPEG (quality 0.8 down to 0.3, then narrower renders) until it is at most 800 kB and answers `workshop_snapshot`; with the tab
hidden the answer carries `error: "hidden"`. Code: `frontend/src/ui/workshop*.ts`, `Stage.snapshot`. Tests: `tests/workshop_logic.mjs` (node),
`tests/workshop.mjs` (DOM harness `tests/workshop_page`, no WebGL).
