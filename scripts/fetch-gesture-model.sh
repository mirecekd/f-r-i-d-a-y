#!/usr/bin/env bash
# scripts/fetch-gesture-model.sh - downloads the MediaPipe hand landmarker model (Apache-2.0) for the hand gestures.
# The file is not committed (about 7 MB). It lands in frontend/public/models/, which Vite copies into the served build.
set -euo pipefail
URL="${GESTURE_MODEL_URL:-https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/frontend/public/models"
mkdir -p "$DIR"
curl -fL --retry 3 -o "$DIR/hand_landmarker.task.part" "$URL"
mv "$DIR/hand_landmarker.task.part" "$DIR/hand_landmarker.task"
echo "saved $DIR/hand_landmarker.task ($(wc -c < "$DIR/hand_landmarker.task") bytes); rebuild the frontend (npm run build) to serve it"
