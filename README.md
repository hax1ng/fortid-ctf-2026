# FortID CTF 2026 — Writeups

Solutions, exploits, and writeups for challenges solved at **FortID CTF 2026**.

- **Event:** FortID CTF 2026 (jeopardy-style)
- **Dates:** Fri 09 Oct 2026, 14:00 EDT — Sun 11 Oct 2026, 14:00 EDT
- **Flag format:** `FortID{...}`
- **By:** [hax1ng](https://github.com/hax1ng)

## Solved challenges

Three solves are written up here, one per category directory.

| Category | Challenge | Writeup | Flag |
|----------|-----------|---------|------|
| Crypto | Hacker Cinema | [writeup](./crypto/hacker-cinema/) | `FortID{F0rg3_7h3_T1ck37_4nd_H4CK_TH3_PL4N3T!_418e3e54f7}` |
| Misc   | Rip & Tear    | [writeup](./misc/rip-and-tear/)    | `FortID{Kn33_Deep_1n_7h3_Fl4gZ!1}` |
| OSINT  | Melankonimir  | [writeup](./osint/melankonimir/)   | `FortID{H4ck1n9_15_7h3_Hev1357_3xerc1s3}` |

## Notable solves

- **Hacker Cinema (crypto).** Forge a signed cinema ticket by triggering
  **ECDSA nonce reuse**: two PHP date APIs (`createFromFormat('U', …)` vs
  `new DateTime('@…')`) disagree around *year zero* on PHP 8.4.16, so the same
  seat bought at two crafted timestamps is signed under the same nonce →
  private-key recovery → a forged `"winner": true` ticket.

- **Rip & Tear (misc).** No flag is ever shown on screen. The challenge patch
  XORs one flag bit into each of Doom's 256 RNG-table entries, and Doom's
  melting-screen transition leaks those values — so the flag is recovered as a
  **side channel**, by measuring melt-column heights frame-by-frame in a
  gameplay recording.

- **Melankonimir (osint).** A clean cross-service pivot chain starting from an
  XMP `Identifier` in the handout image: Civitai → Tumblr → ChatGPT
  shared-conversation links → the Hevy workout tracker → a custom exercise image
  with the flag printed on it.

## Repository layout

```
.
├── crypto/
│   └── hacker-cinema/      ECDSA nonce reuse; vulnerable PHP source + solve.py
├── misc/
│   └── rip-and-tear/       Doom RNG-table side channel; solve.py + patch
└── osint/
    └── melankonimir/       metadata -> multi-service OSINT pivot chain
```

Each challenge directory contains a `README.md` writeup, the final solve
script(s)/exploit, and the relevant challenge artifacts. Some large or
third-party inputs referenced by a writeup (e.g. the Rip & Tear gameplay video,
copyrighted Doom WAD data, a Chocolate Doom checkout) are intentionally **not**
committed; each writeup says what it expects.
