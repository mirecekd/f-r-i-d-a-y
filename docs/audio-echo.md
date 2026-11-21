# Friday hearing herself (echo on phones)

## Why it happens

On a phone the speaker sits millimetres from the microphone. Browser echo cancellation (AEC) works well only when it
knows what is being played: audio from a media element or WebRTC stream is its reference signal. Friday used to play
through Web Audio (`AudioContext.destination`), which Chrome on Android and Safari on iOS do not always use as a
reference, so her own voice came back through the mic, the Live model transcribed it and answered itself.

## The layers

| Layer | Where | What it does |
|---|---|---|
| 1. Media element playback | `frontend/src/audio/player.ts` | Player output -> `MediaStreamDestination` -> hidden `<audio autoplay playsinline>`; created in the mic-button gesture, `play()` awaited. Scheduling (playhead) is unchanged. |
| 2. Mic constraints | `frontend/src/audio/mic.ts` | `echoCancellation {ideal}`, noise suppression, AGC, `voiceIsolation`, `latency: 0`, `googEchoCancellation`; falls back to the basic set on `OverconstrainedError`. The applied settings are logged (`mic settings` in the console). |
| 3. Echo gate | `frontend/src/audio/echogate.ts` | While she speaks (queued audio or server state `speaking`) and 350 ms after, mic chunks are replaced by digital silence unless the user is clearly louder than the learned echo. |
| 4. Server | `backend/app/voice/{session,bridge,selfecho,relay}.py` | `audio_profile: speaker` -> slower turn end at the next session start; a turn that answers Friday's own words is dropped and `notice` "Ozvena potlacena" is shown once. |

The gate is on by default on touch devices (`maxTouchPoints > 0` and an Android/iPhone/iPad/Mobile user agent) and off on
desktop. Settings -> "Zvuk" overrides it and stores `localStorage["friday.headphones"]` (`1` headphones, `0` speaker,
unset = automatic). Headphones cannot be detected reliably, so the choice is manual.

## Knobs

| Name | Default | Where | Effect |
|---|---|---|---|
| `GATE.tailMs` | 350 | echogate.ts | gate stays closed this long after playback ends |
| `GATE.minThreshold` | 0.12 | echogate.ts | lowest barge-in RMS (0..1) |
| `GATE.floorFactor` | 3 | echogate.ts | barge-in must exceed this multiple of the learned echo floor |
| `GATE.bargeMs` | 200 | echogate.ts | loud signal needed this long to open the gate |
| `GATE.learnMs` | 300 | echogate.ts | start of each of her turns only learns the echo floor |
| `GATE.holdMs` | 600 | echogate.ts | gate stays open this long after the last loud frame |
| `GATE.maxFloor` | 0.2 | echogate.ts | cap of the learned floor |
| `SPEAKER_SILENCE_MS` | 900 | session.py | `silence_duration_ms` in speaker profile (headphones: `FRIDAY_VAD_SILENCE_MS`, 700) |
| `SPEAKER_PREFIX_MS` | 300 | session.py | `prefix_padding_ms` in speaker profile (headphones: 200) |
| `selfecho.THRESHOLD` | 0.85 | selfecho.py | similarity needed to call a heard text her own echo |
| `selfecho.WINDOW_S` | 3.0 | selfecho.py | echo is judged against output that ended at most this long ago |
| `relay.DROP_MAX_S` | 8.0 | relay.py | upper bound for ignoring an echo turn if no `turn_complete` arrives |

Side effect of the gate: while she speaks, the user must speak clearly louder than the echo for about 200 ms to
interrupt her; quiet interjections are lost. Switch to "Sluchatka" when wearing headphones.

## What was and was not verified

Verified headless: `pytest` (self-echo matching, `audio_profile` storage and config selection, relay dropping),
`node frontend/tests/echogate.mjs` (simulated echo at 0.05 RMS stays gated, 0.3 RMS speech opens within 200 ms, tail,
adaptation), pyright and the production build. Not verifiable without hardware: whether AEC now cancels the output on a
given phone, the real echo loudness, gapless playback and latency through the `<audio>` element, iOS autoplay behaviour.

## Test on a phone

1. Open Friday on the phone, Settings -> Zvuk -> "Reproduktor". Start the mic and ask for a long answer. Expect: she
   finishes without answering herself, no "Ozvena potlacena" notice (or one at most), console shows
   `mic settings` with `echoCancellation: true`.
2. While she speaks, say something loudly and clearly: she should stop and listen. A whisper should not interrupt.
3. Switch to "Sluchatka" with headphones: barge-in works at normal volume, no gating.
4. If she still hears herself: lower the phone volume, raise `GATE.minThreshold`, or check `mic settings` for
   `echoCancellation: false` (the browser ignored the constraint).
5. Check the playback is gapless and starts promptly after the first words; if the `<audio>` path adds noticeable
   latency, report it (the fallback is `ctx.destination` in `player.ts`).
