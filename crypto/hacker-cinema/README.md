# Hacker Cinema

**Category:** Crypto
**Flag:** `FortID{F0rg3_7h3_T1ck37_4nd_H4CK_TH3_PL4N3T!_418e3e54f7}`

## Description

A small web app lets you reserve a free ticket to a screening of *Hackers*
(1995). Each ticket is a JSON object plus an ECDSA (secp256k1) signature,
rendered into a QR code. Regular tickets always carry `"winner": false`; the
prize checker only hands over the flag when you submit a **validly signed**
ticket with `"winner": true`.

## Initial analysis

Changing any byte of a signed message should break its signature, so forging a
winning ticket looks impossible — unless the signing itself is flawed. Reading
the provided source ([`challenge/`](./challenge)) turns up two suspicious
details:

1. The buy route accepts a hidden `screening` timestamp field that the HTML
   form never exposes, and the accepted range is enormous:

   ```php
   const MIN_SCREENING_TS = -70000000000;   // ~1900 years before year zero
   const MAX_SCREENING_TS = 4102444800;
   ```

   That huge negative lower bound is a loud hint that *old* dates matter.

2. The ticket date and the ECDSA nonce are derived from the timestamp through
   **two different PHP date APIs**:

   ```php
   // ticket date printed on the ticket
   DateTimeImmutable::createFromFormat('U', (string)$ts);
   // date mixed into the deterministic nonce
   new DateTimeImmutable('@' . (string)$ts);
   ```

For modern timestamps these behave identically. For some edge cases they do
not.

## The vulnerability — ECDSA nonce reuse via a PHP calendar quirk

The app derives its "deterministic" ECDSA nonce `k` from an HMAC over a few
ticket fields, including a date produced by `kiosk_partition_date()` — the
`'@'`-based API. The date actually *signed* into the ticket comes from
`ticket_date_from_timestamp()` — the `createFromFormat('U', …)` API. If those
two dates ever disagree for the same seat, two different messages get signed
under the **same nonce**.

Pinning PHP 8.4.16 (as the challenge Dockerfile does) and probing year-zero
timestamps finds exactly such a pair, one day (86,400 s) apart:

```text
timestamp      ticket_date (signed)   kiosk_partition_date (nonce)
-62164800000   0000-01-29             0000-01-29
-62164713600   0000-01-30             0000-01-29
```

The ticket formatter advances to Jan 30 while the nonce partitioner is still on
Jan 29. Buy the same seat at both timestamps → two signatures, same `k`.

Nonce reuse is fatal for ECDSA. With `s = k⁻¹(z + r·d) mod n`, two signatures
`(r, s1)` over `z1` and `(r, s2)` over `z2` that share `k` give:

```text
k = (z1 - z2) · (s1 - s2)⁻¹  mod n
d = (s1·k - z1) · r⁻¹         mod n
```

The repeated `r` value in both signatures is the tell-tale sign of the reuse.
Recovering `k` then recovers the **private signing key** `d`.

Background: [ECDSA nonce reuse / the PS3 "fail0verflow" bug](https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm#Security).

## Exploitation

[`solve.py`](./solve.py) automates the whole chain:

1. POST `/buy` twice with the same seat and the two crafted `screening`
   timestamps.
2. Download each `/ticket.png`, decode the QR with `zbarimg`, and read the
   signed JSON envelope.
3. Confirm the two `r` values match (nonce reuse), then solve for `k` and `d`.
4. Forge a `"winner": true` ticket, sign it with the stolen key (any nonzero
   nonce works now — the solver uses `k = 1`), re-encode it as a QR, and POST
   it to `/check`.

The JSON must be canonicalised exactly like the server (sorted keys, no spaces)
before hashing, and the message hash is `SHA-256` interpreted big-endian and
reduced mod the curve order:

```python
def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def message_hash(ticket):
    digest = hashlib.sha256(canonical_json(ticket).encode()).digest()
    return int.from_bytes(digest, "big") % N
```

## Running it

```bash
python3 solve.py https://<instance-host>        # or http://127.0.0.1:8080 locally
```

```text
[+] ticket dates: 0000-01-29 / 0000-01-30
[+] repeated r: cce12a03ad30c57d48a4a8a2fc3e04daff3c1a69a153aa9b51aed49000dfe422
[+] recovered nonce:      486daf055629d98fa7f509af77bb78472dda5f299634bea2ea8097bba9c9e518
[+] recovered private key: 500569f8c30933fee71549dd60f9b9c23337ddd0052937756348d1a2f86b390c
[+] wrote forged winner QR to forged-ticket-remote.png
[+] flag: FortID{F0rg3_7h3_T1ck37_4nd_H4CK_TH3_PL4N3T!_418e3e54f7}
```

## Key takeaways

- A deterministic nonce is only safe if it is bound to the **exact** bytes
  being signed. Deriving it from a *second*, slightly different representation
  of the message reopens the classic nonce-reuse hole.
- "Equivalent" standard-library calls can diverge at edge cases
  (`createFromFormat('U', …)` vs `new DateTime('@…')` around year zero). Pin and
  test the real runtime instead of trusting that two APIs agree.
- Repeated `r` across two ECDSA signatures = instant private-key recovery.
- Always probe hidden/over-permissive input ranges — the giant negative
  timestamp bound was the whole challenge in one constant.
