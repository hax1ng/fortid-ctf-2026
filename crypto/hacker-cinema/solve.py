#!/usr/bin/env python3
"""Exploit Hacker Cinema's ECDSA nonce reuse."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import qrcode
import requests
from ecdsa.curves import SECP256k1


# These timestamps straddle a PHP timelib year-zero calendar bug.  The ticket
# formatter sees 0000-01-29 and 0000-01-30, while the nonce partitioner sees
# 0000-01-29 for both.
TIMESTAMPS = (-62_164_800_000, -62_164_713_600)
SEAT = "A01"

N = SECP256k1.order
G = SECP256k1.generator


def canonical_json(value: object) -> str:
    """Match canonical_json() for the JSON types used by this challenge."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def decode_qr(image: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp.write(image)
        tmp.flush()
        result = subprocess.run(
            ["zbarimg", "--raw", "-q", tmp.name],
            check=True,
            capture_output=True,
        )
    return result.stdout.decode().splitlines()[0]


def get_ticket(session: requests.Session, base_url: str, timestamp: int) -> dict:
    response = session.post(
        f"{base_url}/buy",
        data={"seat": SEAT, "screening": str(timestamp)},
        allow_redirects=False,
        timeout=15,
    )
    response.raise_for_status()
    location = response.headers.get("Location", "")
    match = re.search(r"[?&]id=([^&]+)", location)
    if not match:
        raise RuntimeError(f"ticket endpoint did not return an id: {location!r}")

    image = session.get(
        f"{base_url}/ticket.png", params={"id": match.group(1)}, timeout=15
    )
    image.raise_for_status()
    return json.loads(decode_qr(image.content))


def message_hash(ticket: dict) -> int:
    digest = hashlib.sha256(canonical_json(ticket).encode()).digest()
    return int.from_bytes(digest, "big") % N


def recover_key(first: dict, second: dict) -> tuple[int, int]:
    r1 = int(first["signature"]["r"], 16)
    r2 = int(second["signature"]["r"], 16)
    if r1 != r2:
        raise RuntimeError("the two signatures did not reuse a nonce")

    s1 = int(first["signature"]["s"], 16)
    s2 = int(second["signature"]["s"], 16)
    z1 = message_hash(first["ticket"])
    z2 = message_hash(second["ticket"])

    k = (z1 - z2) * pow((s1 - s2) % N, -1, N) % N
    private_key = (s1 * k - z1) * pow(r1, -1, N) % N
    return private_key, k


def forge_envelope(private_key: int) -> str:
    ticket = {
        "date": "1995-09-15",
        "movie": "Hackers",
        "screen": "mainframe-1",
        "seat": SEAT,
        "winner": True,
    }
    z = message_hash(ticket)

    # We control the signer now, so a fixed nonzero nonce is sufficient.
    k = 1
    point = k * G
    r = point.x() % N
    s = pow(k, -1, N) * (z + r * private_key) % N
    if s == 0:
        raise RuntimeError("unexpected zero signature scalar")

    envelope = {
        "ticket": ticket,
        "signature": {
            "alg": "ECDSA-secp256k1-SHA256",
            "r": f"{r:064x}",
            "s": f"{s:064x}",
        },
    }
    return canonical_json(envelope)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8080")
    parser.add_argument("--qr-out", default="forged-ticket.png")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    session = requests.Session()
    first = get_ticket(session, base_url, TIMESTAMPS[0])
    second = get_ticket(session, base_url, TIMESTAMPS[1])
    print(f"[+] ticket dates: {first['ticket']['date']} / {second['ticket']['date']}")
    print(f"[+] repeated r: {first['signature']['r']}")

    private_key, nonce = recover_key(first, second)
    print(f"[+] recovered nonce:      {nonce:064x}")
    print(f"[+] recovered private key: {private_key:064x}")

    payload = forge_envelope(private_key)
    qr_path = Path(args.qr_out)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(qr_path)
    print(f"[+] wrote forged winner QR to {qr_path}")

    with qr_path.open("rb") as qr_file:
        response = session.post(
            f"{base_url}/check",
            files={"qr": (qr_path.name, qr_file, "image/png")},
            timeout=15,
        )
    response.raise_for_status()
    flag = re.search(r"FortID\{[^}]+\}", response.text, re.IGNORECASE)
    if not flag:
        raise RuntimeError("forged ticket was not accepted")
    print(f"[+] flag: {flag.group(0)}")


if __name__ == "__main__":
    main()
