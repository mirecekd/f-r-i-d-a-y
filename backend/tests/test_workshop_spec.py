# backend/tests/test_workshop_spec.py
import copy
import math

import pytest

from app.model3d.compile import compile_model
from app.model3d.model import Model, Part
from app.workshop.spec import SpecError, expand, with_params


def spec(*parts, **extra):
    return {"parts": list(parts), **extra}


def box(pid="b", **kw):
    return {"id": pid, "kind": "box", "size": [1, 2, 3], **kw}


def by_id(result):
    return {p["id"]: p for p in result.parts}


def model_of(result, units="mm"):
    return Model.from_dict({"id": "t", "units": units, "parts": result.parts})


def test_every_kind_expands_and_is_accepted_by_model3d():
    result = expand(spec(
        box("box"),
        {"id": "sph", "kind": "sphere", "r": 5},
        {"id": "cyl", "kind": "cylinder", "r": 5, "h": 10},
        {"id": "cone", "kind": "cylinder", "r1": 0, "r2": 5, "h": 10},
        {"id": "frus", "kind": "cylinder", "r1": 3, "r2": 5, "h": 10},
        {"id": "cap", "kind": "capsule", "r": 5, "h": 30},
        {"id": "tor", "kind": "torus", "r": 10, "tube": 3},
        {"id": "pla", "kind": "plane", "size": [4, 6]},
        {"id": "ext", "kind": "extrude", "outline": [[0, 0], [4, 0], [4, 4]], "h": 2},
        {"id": "pol", "kind": "polyline", "pts": [[0, 0, 0], [1, 1, 1]], "width": 2},
        {"id": "lab", "kind": "label", "text": "hi"},
        {"id": "grp", "kind": "group"},
    ))
    parts = by_id(result)
    assert [Part.from_dict(p).id for p in result.parts] == [p["id"] for p in result.parts]
    assert parts["sph"]["scale"] == [10, 10, 10]
    assert parts["cyl"]["kind"] == "cylinder" and parts["cyl"]["scale"] == [10, 10, 10]
    assert parts["cone"]["kind"] == "cone" and parts["cone"]["rot"][0] == pytest.approx(math.pi)
    assert parts["frus"]["kind"] == "cylinder" and parts["frus"]["scale"] == [8, 10, 8]
    assert any("frustum" in n for n in result.notes)
    assert {"cap.body", "cap.top", "cap.bottom"} <= set(parts) and parts["cap"]["kind"] == "group"
    assert parts["cap.top"]["pos"][1] == pytest.approx(10) and parts["cap.top"]["parent"] == "cap"
    assert parts["tor"]["rot"][0] == pytest.approx(math.pi / 2)
    assert parts["pla"]["scale"] == [4, 6, 1] and parts["pla"]["rot"][0] == pytest.approx(-math.pi / 2)
    assert parts["ext"]["geom"] == {"outline": [[0, 0], [4, 0], [4, 4]], "height": 2, "floor": False}
    assert parts["pol"]["geom"]["pts"] == [[0, 0, 0], [1, 1, 1]] and parts["pol"]["props"]["width"] == 2
    assert parts["lab"]["geom"] == {"text": "hi"}
    ops = compile_model(model_of(result))
    assert len(ops) == len(result.parts) + 2


def test_common_fields():
    r = expand(spec({"id": "g", "kind": "group", "pos": [1, 2, 3]},
                    box("b", parent="g", pos=[0, 5, 0], rot=[90, 0, 0], color="#ff0000", tags=["frame", "x"],
                        material={"metal": 0.5, "rough": 0.2, "opacity": 0.4}, name="Beam")))
    b = by_id(r)["b"]
    assert b["parent"] == "g" and b["rot"][0] == pytest.approx(math.pi / 2) and b["color"] == "#ff0000"
    assert b["layer"] == "frame" and b["tags"] == ["frame", "x"] and b["opacity"] == 0.4 and b["name"] == "Beam"
    assert b["props"]["metal"] == 0.5 and b["props"]["source"] == "b"
    assert by_id(r)["g"]["layer"] == "body"


def test_mirror_ids_and_geometry():
    r = by_id(expand(spec(box("arm", pos=[10, 20, 30], rot=[0, 0, 30], mirror="x"))))
    assert set(r) == {"arm", "arm.m"}
    assert r["arm.m"]["pos"] == [-10, 20, 30]
    assert r["arm.m"]["rot"][2] == pytest.approx(-math.radians(30))
    assert r["arm.m"]["props"]["source"] == "arm"


def test_mirror_group_mirrors_children_with_the_group():
    r = by_id(expand(spec({"id": "leg", "kind": "group", "pos": [5, 0, 0], "mirror": "x"},
                          box("foot", parent="leg", pos=[1, 0, 2]))))
    assert set(r) == {"leg", "foot", "leg.m", "foot.m"}
    assert r["leg.m"]["pos"] == [-5, 0, 0] and r["foot.m"]["parent"] == "leg.m" and r["foot.m"]["pos"] == [-1, 0, 2]


def test_mirror_polyline_and_extrude_geometry():
    r = by_id(expand(spec({"id": "pl", "kind": "polyline", "pts": [[1, 2, 3], [4, 5, 6]], "mirror": "x"},
                          {"id": "ex", "kind": "extrude", "outline": [[1, 2], [3, 4], [5, 1]], "h": 1, "mirror": "x"})))
    assert r["pl.m"]["geom"]["pts"] == [[-1, 2, 3], [-4, 5, 6]]
    assert r["ex.m"]["geom"]["outline"] == [[-1, 2], [-3, 4], [-5, 1]]
    with pytest.raises(SpecError, match="mirror 'y' of an extrude"):
        expand(spec({"id": "ex", "kind": "extrude", "outline": [[1, 2], [3, 4], [5, 1]], "h": 1, "mirror": "y"}))


def test_linear_array_and_array_with_mirror():
    r = by_id(expand(spec(box("s", pos=[0, 0, 0], array={"type": "linear", "count": 3, "step": [10, 0, 5]}, mirror="z"))))
    assert set(r) == {"s.0", "s.1", "s.2", "s.0.m", "s.1.m", "s.2.m"}
    assert r["s.2"]["pos"] == [20, 0, 10] and r["s.2.m"]["pos"] == [20, 0, -10]


def test_radial_array():
    r = by_id(expand(spec(box("bl", pos=[0, 5, 0], array={"type": "radial", "count": 4, "axis": "y", "radius": 10}))))
    assert [r[f"bl.{i}"]["pos"] for i in range(4)][0] == [10, 5, 0]
    assert r["bl.1"]["pos"] == pytest.approx([0, 5, -10], abs=1e-5)
    assert r["bl.2"]["pos"] == pytest.approx([-10, 5, 0], abs=1e-5)
    assert r["bl.1"]["rot"][1] == pytest.approx(math.pi / 2)
    z = by_id(expand(spec(box("z", array={"type": "radial", "count": 2, "axis": "z", "radius": 4, "start_deg": 90}))))
    assert z["z.0"]["pos"] == pytest.approx([0, 4, 0], abs=1e-5)
    assert z["z.0"]["rot"][2] == pytest.approx(math.pi / 2)


def test_array_of_group_moves_children():
    r = by_id(expand(spec({"id": "g", "kind": "group", "array": {"type": "linear", "count": 2, "step": [100, 0, 0]}},
                          box("c", parent="g", pos=[1, 0, 0]))))
    assert set(r) == {"g.0", "g.1", "c.0", "c.1"}
    assert r["c.1"]["parent"] == "g.1" and r["g.1"]["pos"] == [100, 0, 0]


def test_units_kept_and_validated():
    r = expand(spec(box(), units="cm"))
    assert model_of(r, "cm").units == "cm"
    with pytest.raises(SpecError, match="units: expected one of mm, cm, m"):
        expand(spec(box(), units="ft"))


def test_params_expressions_defaults_and_clamp_notes():
    r = expand(spec({"id": "t", "kind": "box", "size": ["=w", "=h*2", 5]},
                    params={"w": 40, "h": {"value": 100, "min": 10, "max": 50, "label": "Height", "unit": "mm"}}))
    p = {x["name"]: x for x in r.params}
    assert (p["w"]["min"], p["w"]["max"], p["w"]["label"]) == (4, 200, "w")
    assert p["h"]["value"] == 50 and p["h"]["label"] == "Height" and p["h"]["unit"] == "mm"
    assert any("clamped" in n for n in r.notes)
    assert r.parts[0]["scale"] == [40, 100, 5]
    assert set(p["w"]) == {"name", "label", "value", "min", "max", "step", "unit"}


def test_with_params_is_pure_and_clamped():
    s = spec({"id": "t", "kind": "box", "size": ["=w", 1, 1]}, params={"w": {"value": 10, "min": 5, "max": 20}})
    before = copy.deepcopy(s)
    out = with_params(s, {"w": 99})
    assert s == before and out is not s
    assert expand(out).params[0]["value"] == 20 and expand(out).parts[0]["scale"][0] == 20
    assert with_params(s, {"w": 1})["params"]["w"]["value"] == 5
    with pytest.raises(SpecError, match="params.q: unknown parameter"):
        with_params(s, {"q": 1})
    with pytest.raises(SpecError, match="finite"):
        with_params(s, {"w": float("nan")})
