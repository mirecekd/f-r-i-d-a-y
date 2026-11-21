# backend/tests/test_workshop_expr.py
import math

import pytest

from app.workshop.expr import SpecError, evaluate, number

ENV = {"width": 10.0, "height": 4.0}


def ev(text: str, env=ENV) -> float:
    return evaluate(text, env, "f")


def test_precedence_and_unary():
    assert ev("1+2*3") == 7
    assert ev("(1+2)*3") == 9
    assert ev("-2+5") == 3
    assert ev("--2") == 2
    assert ev("10-4-3") == 3
    assert ev("8/4/2") == 1
    assert ev("7%4") == 3


def test_power_right_associative():
    assert ev("2^3^2") == 512
    assert ev("2^-1") == 0.5
    assert ev("-2^2") == -4


def test_functions_and_constants():
    assert ev("min(3,1,2)") == 1
    assert ev("max(3,1,2)") == 3
    assert ev("abs(-3)") == 3
    assert ev("sqrt(16)") == 4
    assert ev("sin(0)") == 0
    assert ev("cos(0)") == 1
    assert ev("tan(0)") == 0
    assert ev("atan2(1,1)") == pytest.approx(math.pi / 4)
    assert ev("clamp(15,0,10)") == 10
    assert ev("round(2.5)") == 3
    assert ev("floor(2.9)") == 2
    assert ev("ceil(2.1)") == 3
    assert ev("pi") == pytest.approx(math.pi)
    assert ev("width*0.5+height") == 9


def test_number_helper():
    assert number(3, ENV, "f") == 3.0
    assert number("=width/2", ENV, "f") == 5.0
    for bad in ("5", True, None, [1], float("nan"), float("inf"), 1e12):
        with pytest.raises(SpecError, match="^f:"):
            number(bad, ENV, "f")


@pytest.mark.parametrize("text", ["1/0", "5%0", "sqrt(-1)", "9^9^9", "10^400", "tan(pi/2)*1e300", "1e300*1e300", "(-8)^0.5"])
def test_math_errors_name_the_field(text):
    with pytest.raises(SpecError, match="^f:"):
        ev(text)


def test_unknown_name_lists_known_parameters():
    with pytest.raises(SpecError, match=r"f: unknown parameter 'wdth'; did you mean 'width'\?") as e:
        ev("wdth*2")
    assert "height" in str(e.value)
    with pytest.raises(SpecError, match="known: "):
        ev("zzzz", {"a": 1.0})
    with pytest.raises(SpecError, match="unknown function 'sinn'; did you mean 'sin'"):
        ev("sinn(1)")


def test_argument_count():
    for text in ("sqrt()", "sqrt(1,2)", "min(1)", "clamp(1,2)"):
        with pytest.raises(SpecError, match="f:"):
            ev(text)


@pytest.mark.parametrize(
    "text",
    ["__import__('os')", "1;2", "width.real", "'abc'", "lambda x: x", "[1,2]", "width if 1 else 2", "1 2", "(1", "1)", "", "+",
     "2 **3", "a=1", "$x", "1,2", "__class__", "().__class__", "1_0", "0x10", "1e", "not 1", "{}"],
)
def test_injection_and_garbage_refused(text):
    with pytest.raises(SpecError, match="^f:"):
        ev(text)


def test_limits():
    with pytest.raises(SpecError, match="longer than 160"):
        ev("1+" * 80 + "1")
    with pytest.raises(SpecError, match="deeper than 12"):
        ev("(" * 13 + "1" + ")" * 13)
    assert ev("(" * 5 + "1" + ")" * 5) == 1
    assert ev("+".join(["1"] * 80)) == 80  # 159 nodes, 159 characters: still allowed


def test_node_limit(monkeypatch):
    monkeypatch.setattr("app.workshop.expr.MAX_NODES", 5)
    with pytest.raises(SpecError, match="more than 5 nodes"):
        ev("1+1+1+1")
    assert ev("1+1") == 2


def test_depth_limits_unary_and_calls():
    with pytest.raises(SpecError, match="deeper than 12"):
        ev("-" * 13 + "1")
    with pytest.raises(SpecError, match="deeper than 12"):
        ev("sin(" * 13 + "1" + ")" * 13)
