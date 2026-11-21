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

## Hand gestures

A webcam tracks both hands (MediaPipe HandLandmarker, in the browser). Enable it with the open-hand button in the dock (next
to the magnifier); a small draggable preview shows the mirrored video, the 21-point skeleton and the current gesture. The
first time it shows "Postav se tak, aby byly videt obe ruce". The on/off state is kept in `localStorage` key `friday.gestures`.

| Gesture | Effect |
|---|---|
| Two hands apart / together | Scale the held entity, or dolly the camera when nothing is held (ratio of the current hand distance to the distance at the start) |
| One-hand pinch (thumb + index) and move | Grab and move the entity under the pinch; pan the camera when nothing is there |
| Pinch with both hands on an entity | Rotate it by the angle of the line between the hands (about the camera axis); with no entity the camera orbits |
| Cross the arms (X, held 400 ms) | Close the topmost open panel; during a drag it cancels the drag and restores the start state |
| Open palm held still for 600 ms (one hand) | `{t:'stop'}`, only if "Otevrena dlan = Stop" is ticked in Settings > Gesta rukou (default off) |
| Fist | Release |
| Both hands wide and flat | Explode the scene (`explode` op, factor proportional to the spread, at most ~8 per second); bringing the hands together restores it |

Recognition (`gesture/logic.ts`, pure): pinch = thumb tip to index tip over palm size (wrist to middle MCP) below 0.35, released above 0.5;
open palm = every fingertip farther from the wrist than its PIP joint; fist = all four fingers curled. Poses need 3 frames,
landmarks are exponentially smoothed, a hand lost for under 150 ms keeps its state and one lost for over 300 ms releases.
The logic works in mirrored screen space and ignores the handedness label for identity.

### Test without a camera

- Pure logic: `cd frontend && node --experimental-strip-types tests/gesture_logic.mjs` (synthetic landmark sequences).
- Mapper without a camera: open the app with `?gesturedemo` and drive it with the mouse: hold `G` and drag right/left = scale,
  `R` + drag = rotate, `M` + drag = move, `F` + drag right = flatten, `H` = close the topmost panel, `S` = stop gesture
  (honours the setting), `Esc` during a drag = cancel. The pointed entity is the one under the cursor when the drag starts.

### Model download

The model and the wasm runtime are not committed. The wasm comes from the npm package `@mediapipe/tasks-vision` (Apache-2.0)
as a lazily loaded chunk. The model `hand_landmarker.task` (Apache-2.0, Google MediaPipe) is fetched once with
`scripts/fetch-gesture-model.sh` from
`https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`
into `frontend/public/models/` (git-ignored; copied to the served build by `npm run build`). The app requests
`/models/hand_landmarker.task` (override with `?gesturemodel=<url>`); when it is missing the preview says
"Model gest neni nainstalovan: spust scripts/fetch-gesture-model.sh". The backend must serve the `/models` directory of its static root.

### Privacy

The camera video never leaves the browser and nothing is stored: frames go only to the local MediaPipe runtime and landmarks
are discarded after each frame. Only the on/off flag and the stop-gesture flag are saved in `localStorage`. Tracking pauses to
about 1 frame per second while the tab is hidden. If the dock camera is already streaming, its stream is reused, otherwise the
tracker opens its own front camera after the click.

Code: `gesture/{hand,tracks,crossing,logic,events}.ts` (pure), `gesture/{mapper,cammove}.ts` (scene), `gesture/{tracker,demo,prefs}.ts`
(glue), `ui/{gesturebtn,gesturepreview}.ts` (UI).
