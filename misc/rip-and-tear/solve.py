#!/usr/bin/env python3
"""Recover the Rip & Tear flag from Doom's melting-screen transition.

The challenge patch XORs one flag bit into each of the 256 entries of Doom's
random-number table. Doom's screen-wipe effect ("the melt") uses those random
values to pick each column's starting delay, so measuring column heights during
a few wipes in the gameplay recording leaks the modified random values, and with
them one flag bit per table entry.

Expects, in the current directory:
  - gameplay.mkv          the challenge recording
  - src_repo/             a Chocolate Doom checkout (for the pristine rndtable)

    git clone https://github.com/chocolate-doom/chocolate-doom src_repo
    python3 -m pip install numpy opencv-python
    python3 solve.py
"""

from pathlib import Path
import re

import cv2
import numpy as np


VIDEO = "gameplay.mkv"
RANDOM_C = "src_repo/src/doom/m_random.c"

# before frame, middle frame, after frame, first table entry, wipe tick count.
# The first two wipes sit between mostly static screens, so their pixel
# measurements are the cleanest; the third only fills the one remaining byte.
WIPES = [
    (116,   155,   180,   232, 25),  # static title/menu wipe
    (11127, 11155, 11184, 144, 17),  # static intermission wipe
    (349,   373,   410,     2, 23),  # fills bits 136-143
]


def read_native_frame(cap, frame_no):
    """Grab a frame and rescale it to Doom's native 320x200 render."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError(f"Could not read frame {frame_no}")

    # Crop off the black border, then restore the native resolution.
    frame = frame[29:1049, 280:1640]
    return cv2.resize(frame, (320, 200), interpolation=cv2.INTER_AREA)


def fit_boundaries(old, new, observed):
    """For each of the 160 melt columns, find the melt height that best
    explains the observed mid-wipe frame (new screen on top, old below)."""
    old = old.astype(np.int16)
    new = new.astype(np.int16)
    observed = observed.astype(np.int16)

    height = observed.shape[0]
    cuts = []

    for i in range(160):
        # Chocolate Doom packs two neighbouring pixels into one melt column.
        column = slice(2 * i, 2 * i + 2)
        errors = []

        for cut in range(height + 1):
            predicted = np.concatenate(
                (new[:cut, column], old[:height - cut, column]),
                axis=0,
            )
            errors.append(np.abs(predicted - observed[:, column]).mean())

        cuts.append(int(np.argmin(errors)))

    return np.array(cuts)


def melt_distance(active_ticks):
    """Visible fall distance after this many active melt ticks."""
    y = 0
    for _ in range(active_ticks):
        amount = y + 1 if y < 16 else 8
        y = min(200, y + amount)
    return y


DISTANCES = np.array([melt_distance(q) for q in range(50)])


def recover_initial_y(old, new, observed, total_ticks):
    """Convert measured melt heights back into each column's initial y delay."""
    cuts = fit_boundaries(old, new, observed)

    # Match each measured height to the nearest achievable "active ticks" count.
    active_ticks = np.abs(cuts[:, None] - DISTANCES[None, :]).argmin(axis=1)

    # A column that starts at -k spends k ticks waiting before it falls.
    return active_ticks - total_ticks


def recover_bit_options(rndtable, start_index, y):
    """Given the recovered y path, deduce which flag bits are consistent with
    each random-table entry used during this wipe."""
    options = [set((0, 1)) for _ in range(256)]

    # f_wipe.c: y[0] = -(M_Random() % 16)
    idx = start_index
    options[idx] = {
        bit for bit in (0, 1)
        if -((rndtable[idx] ^ bit) % 16) == y[0]
    }

    # f_wipe.c: y[i] = clamp(y[i-1] + (M_Random() % 3) - 1)
    for i in range(1, 160):
        idx = (start_index + i) & 0xFF
        valid = set()

        for bit in (0, 1):
            next_y = y[i - 1] + ((rndtable[idx] ^ bit) % 3) - 1
            if next_y > 0:
                next_y = 0
            elif next_y == -16:
                next_y = -15

            if next_y == y[i]:
                valid.add(bit)

        options[idx] = valid

    return options


def set_known_text(bits, character_offset, text):
    """Pin the bits of a known flag substring (the FortID{ prefix and } suffix)."""
    for position, value in enumerate(text.encode()):
        for j in range(8):
            bits[8 * (character_offset + position) + j] = (value >> (7 - j)) & 1


def main():
    # Pristine 256-byte random table straight from Chocolate Doom's source.
    source = Path(RANDOM_C).read_text()
    body = re.search(r"rndtable\[256\].*?=\s*\{(.*?)\};", source, re.S).group(1)
    rndtable = list(map(int, re.findall(r"\d+", body)))
    assert len(rndtable) == 256

    bits = [None] * 256

    # Known from the flag format and the patch's asserted 32-byte length.
    set_known_text(bits, 0, "FortID{")
    set_known_text(bits, 31, "}")

    cap = cv2.VideoCapture(VIDEO)

    # Clean static wipes first; the noisy gameplay wipe only fills what's left.
    for before_no, middle_no, after_no, start, ticks in WIPES:
        old = read_native_frame(cap, before_no)
        observed = read_native_frame(cap, middle_no)
        new = read_native_frame(cap, after_no)

        y = recover_initial_y(old, new, observed, ticks)
        options = recover_bit_options(rndtable, start, y)

        for i, choices in enumerate(options):
            if bits[i] is None and len(choices) == 1:
                bits[i] = next(iter(choices))

    assert all(bit is not None for bit in bits)

    flag = "".join(
        chr(sum(bits[8 * i + j] << (7 - j) for j in range(8)))
        for i in range(32)
    )
    print(flag)


if __name__ == "__main__":
    main()
