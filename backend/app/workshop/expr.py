# backend/app/workshop/expr.py
"""Tiny safe expression evaluator for spec fields (hand-written tokenizer and recursive descent, no eval)."""

import difflib
import math
import re
from collections.abc import Callable, Iterable, Mapping

MAX_LEN, MAX_DEPTH, MAX_NODES, MAX_ABS = 160, 12, 200, 1e9
_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z_]\w*)|([-+*/^%(),]))")
CONSTANTS = {"pi": math.pi}


class SpecError(ValueError):
    """A spec problem; the message names the bad field, e.g. "parts[3].size[1]: unknown parameter 'wdth'"."""


def did_you_mean(word: str, known: Iterable[str]) -> str:
    """Suffix for an unknown-name message: the closest known name (if any) and the known names."""
    names = sorted(known)
    close = difflib.get_close_matches(word, names, n=1)
    hint = f"; did you mean '{close[0]}'?" if close else ""
    return f"{hint} known: {', '.join(names[:30])}" if names else hint


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def _min(*xs: float) -> float:
    return min(xs)


def _max(*xs: float) -> float:
    return max(xs)


def _abs(x: float) -> float:
    return abs(x)


def _round(x: float) -> float:
    return float(math.floor(x + 0.5))


FUNCTIONS: dict[str, tuple[Callable[..., float], int, int]] = {  # name -> (fn, min args, max args)
    "min": (_min, 2, 8), "max": (_max, 2, 8), "abs": (_abs, 1, 1), "sqrt": (math.sqrt, 1, 1), "sin": (math.sin, 1, 1),
    "cos": (math.cos, 1, 1), "tan": (math.tan, 1, 1), "atan2": (math.atan2, 2, 2), "clamp": (_clamp, 3, 3),
    "round": (_round, 1, 1), "floor": (lambda x: float(math.floor(x)), 1, 1), "ceil": (lambda x: float(math.ceil(x)), 1, 1),
}


def _tokens(text: str, path: str) -> list[tuple[str, str]]:
    out, i = [], 0
    while text[i:].strip():
        m = _TOKEN.match(text, i)
        if not m:
            raise SpecError(f"{path}: unexpected character {text[i:].lstrip()[0]!r} in expression {text!r}")
        out.append(("num", m[1]) if m[1] else ("name", m[2]) if m[2] else ("op", m[3]))
        i = m.end()
    return out


class _Parser:
    def __init__(self, text: str, env: Mapping[str, float], path: str):
        self.toks, self.i, self.env, self.path, self.depth, self.nodes = _tokens(text, path), 0, env, path, 0, 0

    def fail(self, msg: str) -> SpecError:
        return SpecError(f"{self.path}: {msg}")

    def peek(self) -> tuple[str, str]:
        return self.toks[self.i] if self.i < len(self.toks) else ("end", "")

    def take(self, op: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok[0] == "end" or (op is not None and tok != ("op", op)):
            raise self.fail(f"expected '{op}'" if op else "expression ends too early")
        self.i += 1
        return tok

    def node(self, value: float) -> float:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise self.fail(f"expression has more than {MAX_NODES} nodes")
        if not math.isfinite(value) or abs(value) > MAX_ABS:
            raise self.fail("result is not a finite number below 1e9")
        return value

    def parse(self) -> float:
        value = self.expr()
        if self.peek()[0] != "end":
            raise self.fail(f"unexpected {self.peek()[1]!r} in expression")
        return value

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.fail(f"expression nests deeper than {MAX_DEPTH}")

    def expr(self) -> float:
        self.enter()
        v = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            r = self.term()
            v = self.node(v + r if op == "+" else v - r)
        self.depth -= 1
        return v

    def term(self) -> float:
        v = self.unary()
        while self.peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self.take()[1]
            r = self.unary()
            if op != "*" and r == 0:
                raise self.fail("division by zero")
            v = self.node(v * r if op == "*" else v / r if op == "/" else math.fmod(v, r))
        return v

    def unary(self) -> float:
        if self.peek() in (("op", "-"), ("op", "+")):
            self.enter()
            neg = self.take()[1] == "-"
            v = self.unary()
            self.depth -= 1
            return self.node(-v if neg else v)
        base = self.atom()
        if self.peek() == ("op", "^"):
            self.take()
            self.enter()
            exp = self.unary()
            self.depth -= 1
            try:
                return self.node(math.pow(base, exp))
            except (ValueError, OverflowError):
                raise self.fail("power is undefined or too large") from None
        return base

    def atom(self) -> float:
        kind, text = self.take()
        if kind == "num":
            return self.node(float(text))
        if kind == "op" and text == "(":
            v = self.expr()
            self.take(")")
            return v
        if kind != "name":
            raise self.fail(f"unexpected {text!r} in expression")
        if self.peek() == ("op", "("):
            return self.call(text)
        if text in CONSTANTS:
            return self.node(CONSTANTS[text])
        if text in self.env:
            return self.node(float(self.env[text]))
        raise self.fail(f"unknown parameter '{text}'" + did_you_mean(text, [*self.env, *CONSTANTS]))

    def call(self, name: str) -> float:
        if name not in FUNCTIONS:
            raise self.fail(f"unknown function '{name}'" + did_you_mean(name, FUNCTIONS))
        fn, lo, hi = FUNCTIONS[name]
        self.take("(")
        self.enter()
        args = [self.expr()]
        while self.peek() == ("op", ","):
            self.take()
            args.append(self.expr())
        self.take(")")
        self.depth -= 1
        if not lo <= len(args) <= hi:
            raise self.fail(f"{name}() takes {lo}..{hi} arguments, got {len(args)}")
        try:
            return self.node(float(fn(*args)))
        except (ValueError, OverflowError, ZeroDivisionError):
            raise self.fail(f"{name}() is undefined for these arguments") from None


def evaluate(text: str, env: Mapping[str, float], path: str) -> float:
    if len(text) > MAX_LEN:
        raise SpecError(f"{path}: expression is longer than {MAX_LEN} characters")
    return _Parser(text, env, path).parse()


def number(value: object, env: Mapping[str, float], path: str) -> float:
    """A spec number: a plain finite number, or a string starting with '=' holding an expression."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SpecError(f"{path}: expected a number or an '=expression', got {type(value).__name__}")
    if isinstance(value, str):
        if not value.startswith("="):
            raise SpecError(f"{path}: a string value must start with '=' to be an expression, got {value!r}")
        return evaluate(value[1:], env, path)
    if not math.isfinite(value) or abs(value) > MAX_ABS:
        raise SpecError(f"{path}: number must be finite and below 1e9")
    return float(value)
