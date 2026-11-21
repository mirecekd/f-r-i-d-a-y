# UI gestures (client only)

## Zoom by drawing

Draw an outline on the screen and the 3D view zooms to it.

- Enable with the magnifier button in the dock or the `Z` key; on a desktop hold `Shift` and drag without any button.
- Drag draws a glowing freehand outline with a dashed bounding rectangle (it does not orbit). Release zooms. `Esc` cancels.
- Strokes shorter than 12 px are taps and are left to selection.
- Top-level objects whose projected bounds are at least half inside the rectangle are framed together. With no object, the camera targets the rectangle centre (camera-facing plane through the orbit target) and dollies so the rectangle fills the viewport.
- Release with `Alt` or `Ctrl` to select the enclosed objects instead (sends `{t:'select', ids}`).
- Every zoom pushes the previous view on a history (max 20): `ZPET` button or `Backspace` pops. Double-tap on empty space (or `Home`) returns to the home view saved at load.
- With zoom mode off the overlay ignores pointers, so one-finger orbit and two-finger pinch/pan are unchanged. With it on, the overlay has `touch-action: none`.

Code: `ui/zoombox.ts` (controller), `ui/zoomdraw.ts` (canvas), `core/zoommath.ts` (math).
