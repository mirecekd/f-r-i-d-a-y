# backend/app/scene_demo_gltf.py
"""A tiny self-contained glTF (tetrahedron) as a data URI, so the demo needs no network or asset files."""

import base64
import json
import struct


def tetrahedron_data_uri() -> str:
    verts = [1, 1, 1, -1, -1, 1, -1, 1, -1, 1, -1, -1]
    idx = [0, 1, 2, 0, 3, 1, 0, 2, 3, 1, 3, 2]
    blob = struct.pack("<12f12H", *verts, *idx)
    doc = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(blob), "uri": "data:application/octet-stream;base64," + base64.b64encode(blob).decode()}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 48, "target": 34962},
            {"buffer": 0, "byteOffset": 48, "byteLength": 24, "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3", "min": [-1, -1, -1], "max": [1, 1, 1]},
            {"bufferView": 1, "componentType": 5123, "count": 12, "type": "SCALAR"},
        ],
    }
    return "data:model/gltf+json;base64," + base64.b64encode(json.dumps(doc).encode()).decode()
