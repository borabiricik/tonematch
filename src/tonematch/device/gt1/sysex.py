"""Roland address-mapped SysEx (DT1 / RQ1) as used by BOSS TONE STUDIO for GT-1."""

from __future__ import annotations

ROLAND = 0x41
DT1 = 0x12
RQ1 = 0x11
IDENTITY_REQUEST = bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])


def checksum(payload: list[int] | bytes) -> int:
    return (128 - sum(payload) % 128) % 128


def dt1(dev: int, model: list[int], addr: list[int], data: list[int] | bytes) -> bytes:
    body = [*addr, *data]
    if any(not 0 <= b <= 0x7F for b in body):
        raise ValueError("SysEx payload must be 7-bit")
    return bytes([0xF0, ROLAND, dev, *model, DT1, *body, checksum(body), 0xF7])


def rq1(dev: int, model: list[int], addr: list[int], size: int) -> bytes:
    sz = [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    body = [*addr, *sz]
    return bytes([0xF0, ROLAND, dev, *model, RQ1, *body, checksum(body), 0xF7])


def parse_dt1(msg: bytes | list[int], model: list[int]) -> tuple[list[int], list[int]] | None:
    """Return (address, data) for a DT1 from this model, else None."""
    m = list(msg)
    head = 3 + len(model)
    if len(m) < head + 7 or m[0] != 0xF0 or m[1] != ROLAND or m[-1] != 0xF7:
        return None
    if m[3:head] != list(model) or m[head] != DT1:
        return None
    body = m[head + 1:-2]
    if checksum(body) != m[-2]:
        return None
    return body[:4], body[4:]


def addr_add(addr: list[int], n: int) -> list[int]:
    """Advance a 4-byte 7-bit address by n."""
    v = 0
    for b in addr:
        v = (v << 7) | b
    v += n
    return [(v >> 21) & 0x7F, (v >> 14) & 0x7F, (v >> 7) & 0x7F, v & 0x7F]


def parse_addr(s: str) -> list[int]:
    return [int(x, 16) for x in s.split(",")]
