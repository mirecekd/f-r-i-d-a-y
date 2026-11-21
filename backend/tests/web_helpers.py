# backend/tests/web_helpers.py
"""Fake network for the web page tests: scripted HTTP answers, a fake resolver, and a counter of real connections."""

import httpcore

PUBLIC_IP = "93.184.216.34"


def http_answer(status: int = 200, ctype: str | None = "text/html; charset=utf-8", body: bytes = b"<p>hi</p>",
                extra: dict[str, str] | None = None, length: bool = True) -> bytes:
    head = [f"HTTP/1.1 {status} X"]
    if ctype:
        head.append(f"Content-Type: {ctype}")
    if length:
        head.append(f"Content-Length: {len(body)}")
    head += [f"{k}: {v}" for k, v in (extra or {}).items()]
    return ("\r\n".join(head) + "\r\n\r\n").encode() + body


def redirect(location: str, status: int = 302) -> bytes:
    return http_answer(status, None, b"", {"Location": location})


class FakeNet:
    """Hands out one scripted answer per hop; `connects` lists the IPs the fetcher tried to connect to."""

    def __init__(self, answers: list[bytes], peer: str | None = None) -> None:
        self.answers = list(answers)
        self.connects: list[str] = []
        self.sent: list[bytes] = []
        self.peer = peer

    def factory(self, ip: str) -> httpcore.AsyncNetworkBackend:
        self.connects.append(ip)
        return _Backend(ip, self.answers.pop(0) if self.answers else b"", self.peer, self.sent)


class _Stream(httpcore.AsyncMockStream):
    def __init__(self, chunks: list[bytes], peer: str, sent: list[bytes]) -> None:
        super().__init__(chunks)
        self.peer, self.sent = peer, sent

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.sent.append(buffer)

    def get_extra_info(self, info: str):
        return (self.peer, 443) if info == "server_addr" else None


class _Backend(httpcore.AsyncMockBackend):
    def __init__(self, ip: str, answer: bytes, peer: str | None, sent: list[bytes]) -> None:
        super().__init__([answer])
        self.ip, self.answer, self.peer, self.sent = ip, answer, peer, sent
        self.connected_to: str | None = None

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected_to = self.peer or self.ip
        return _Stream([self.answer], self.connected_to, self.sent)


def resolver(table: dict[str, list[str]]):
    calls: list[str] = []

    async def resolve(host: str, port: int) -> list[str]:
        calls.append(host)
        if host not in table:
            raise OSError("no such host")
        return table[host]

    resolve.calls = calls  # type: ignore[attr-defined]
    return resolve
