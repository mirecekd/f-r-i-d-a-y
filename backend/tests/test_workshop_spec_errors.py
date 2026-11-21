# backend/tests/test_workshop_spec_errors.py
import copy

import pytest

from app.workshop.spec import SpecError, expand


def spec(*parts, **extra):
    return {"parts": list(parts), **extra}


def box(pid="b", **kw):
    return {"id": pid, "kind": "box", "size": [1, 2, 3], **kw}


@pytest.mark.parametrize("bad,match", [
    ({"parts": [box()], "colr": "x"}, "colr: unknown key"),
    (spec(box(sise=[1, 1, 1])), r"parts\[0\].sise: unknown key"),
    (spec({"id": "a", "kind": "boxx"}), r"parts\[0\].kind: unknown kind 'boxx'; did you mean 'box'"),
    (spec(box("a"), box("a")), r"parts\[1\].id: duplicate id 'a'"),
    (spec(box("a", parent="zz")), r"parts\[0\].parent: unknown part 'zz'"),
    (spec(box("a"), box("b", parent="a")), "only a group can hold parts"),
    (spec({"id": "a", "kind": "group", "parent": "b"}, {"id": "b", "kind": "group", "parent": "a"}), "cycle"),
    (spec({"id": "a", "kind": "box", "size": [1, 1, "=wdth"]}, params={"width": 3}), r"parts\[0\].size\[2\]: unknown parameter 'wdth'; did you mean 'width'"),
    (spec({"id": "a", "kind": "box", "size": [1, 1]}), r"parts\[0\].size: expected a list of 3 numbers"),
    (spec({"id": "a", "kind": "box", "size": [1, 0, 1]}), r"parts\[0\].size\[1\]: must be > 0"),
    (spec({"id": "a", "kind": "box"}), r"parts\[0\].size: required"),
    (spec({"id": "a b", "kind": "box", "size": [1, 1, 1]}), r"parts\[0\].id"),
    (spec(box(), params={"w": {"valu": 1}}), r"params.w.valu: unknown key; did you mean 'value'"),
    (spec(box(), params={"w": {"value": 1, "min": 5, "max": 2}}), "min 5 is greater than max 2"),
    (spec(box(), params={"pi": 3}), "invalid parameter name"),
    (spec(box(mirror="w")), r"parts\[0\].mirror"),
    (spec(box(array={"type": "ring", "count": 2})), r"parts\[0\].array.type"),
    (spec(box(array={"type": "linear", "count": 201, "step": [1, 0, 0]})), r"parts\[0\].array.count: must be between 1 and 200"),
    (spec(box(array={"type": "linear", "count": 2, "stp": [1, 0, 0]})), r"array.stp: unknown key; did you mean 'step'"),
    (spec(box(array={"type": "radial", "count": 2, "axis": "q"})), r"array.axis"),
    (spec({"id": "c", "kind": "cylinder", "r": 1, "r1": 1, "r2": 2, "h": 1}), "either 'r' or both"),
    (spec({"id": "c", "kind": "capsule", "r": 5, "h": 8}), "capsule height 8 must be at least"),
    (spec({"id": "c", "kind": "sphere", "r": "5"}), "must start with '='"),
    (spec(), "parts: expected a non-empty list"),
    ({"parts": [box()], "extra": 1}, "extra: unknown key"),
    ([], "expected an object"),
])
def test_validation_errors_name_the_field(bad, match):
    with pytest.raises(SpecError, match=match):
        expand(bad)


def test_caps():
    with pytest.raises(SpecError, match="params: at most 40"):
        expand(spec(box(), params={f"p{i}": 1 for i in range(41)}))
    assert len(expand(spec(box(), params={f"p{i}": 1 for i in range(40)})).params) == 40
    big = {"type": "linear", "count": 200, "step": [1, 0, 0]}
    with pytest.raises(SpecError, match="expands to 2400 parts, the limit is 2000"):
        expand(spec(*[box(f"b{i}", array=big, mirror="x") for i in range(6)]))
    assert len(expand(spec(*[box(f"b{i}", array=big, mirror="x") for i in range(5)])).parts) == 2000


def test_group_depth_cap():
    chain = [{"id": f"g{i}", "kind": "group", **({"parent": f"g{i - 1}"} if i else {})} for i in range(7)]
    with pytest.raises(SpecError, match="nested deeper than 6"):
        expand(spec(*chain))
    assert len(expand(spec(*chain[:6])).parts) == 6


def test_spec_ids_cannot_clash_with_generated_ids():
    with pytest.raises(SpecError, match=r"parts\[1\].id"):
        expand(spec(box("a", mirror="x"), box("a.m")))


def test_expansion_is_deterministic():
    s = spec(box("a", mirror="x", array={"type": "radial", "count": 5, "axis": "y", "radius": 3}))
    assert expand(s).parts == expand(copy.deepcopy(s)).parts
