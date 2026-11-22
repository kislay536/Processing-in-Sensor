"""Bit-exact golden models of the three hardware detectors (pure integer arithmetic, mirrors hls/*.cpp).

ChangeDetector  - colour camera (Y of YUYV 640x480 -> 128x96) and IR camera (GREY 480x480 -> 96x96):
                  5x5 box mean (floor), per-pixel background bg16 (4 fractional bits), changed = |cur - bg| > pix_thresh.
GoertzelBands   - microphone, 512-sample blocks (32 ms at 16 kHz), 8 bands of 3 adjacent 31.25 Hz bins each.
Only the per-frame/per-block SCORES are computed here (and in the PL); the trigger decision (baseline, K-of-N, fusion) lives in firmware.
"""
import math
from dataclasses import dataclass

import numpy as np

N_BLOCK = 512
COEF_SHIFT = 14
BAND_CENTRE_BINS = [4, 8, 16, 32, 64, 96, 128, 192]            # 125, 250, 500, 1000, 2000, 3000, 4000, 6000 Hz
BAND_HZ = [k * 16000 // N_BLOCK for k in BAND_CENTRE_BINS]
BINS = [k + d for k in BAND_CENTRE_BINS for d in (-1, 0, 1)]   # 24 Goertzel filters
COEFS = [round(2 * math.cos(2 * math.pi * k / N_BLOCK) * (1 << COEF_SHIFT)) for k in BINS]


def box5(y: np.ndarray) -> np.ndarray:
    h, w = y.shape
    s = y.astype(np.uint32).reshape(h // 5, 5, w // 5, 5).sum(axis=(1, 3))
    return (s // 25).astype(np.uint8)


@dataclass
class ChangeDetector:
    pix_thresh: int = 24
    bg_shift: int = 3
    bg16: np.ndarray = None

    def step(self, small: np.ndarray, reset: bool = False):
        """small: uint8 (h,w) box-downscaled Y. Returns (changed_count, sum_cur)."""
        cur = small.astype(np.int32)
        if reset or self.bg16 is None:
            self.bg16 = cur * 16
        diff = np.abs(cur - (self.bg16 >> 4))
        changed = int((diff > self.pix_thresh).sum())
        self.bg16 = self.bg16 + ((cur * 16 - self.bg16) >> self.bg_shift)
        return changed, int(cur.sum())

    def step_raw(self, y: np.ndarray, reset: bool = False):
        return self.step(box5(y), reset)


def goertzel_bands(x):
    """x: 512 int16 samples. Returns (list of 8 band powers as Python ints, sum of squares)."""
    x = [int(v) for v in x]
    assert len(x) == N_BLOCK
    powers = []
    for coef in COEFS:
        s1 = s2 = 0
        for v in x:
            s0 = v + ((coef * s1) >> COEF_SHIFT) - s2
            s2, s1 = s1, s0
        powers.append(s1 * s1 + s2 * s2 - ((coef * s1 * s2) >> COEF_SHIFT))
    bands = [sum(powers[3 * b:3 * b + 3]) for b in range(8)]
    return bands, sum(v * v for v in x)


def goertzel_bands_fast(x):
    """Same arithmetic, vectorised over the 24 filters with Python ints kept exact via object arrays (used on long recordings)."""
    xs = np.asarray(x, dtype=np.int64)
    coef = np.array(COEFS, dtype=np.int64)
    s1 = np.zeros(len(COEFS), dtype=np.int64); s2 = np.zeros(len(COEFS), dtype=np.int64)
    for v in xs:
        s0 = v + ((coef * s1) >> COEF_SHIFT) - s2        # |s| < 2^26, coef < 2^15: product < 2^41, fits int64
        s2, s1 = s1, s0
    # final power needs up to 2^26 * 2^26 * 2^15 = 2^67: do the last step in Python ints
    out = []
    for c, a, b in zip(COEFS, s1.tolist(), s2.tolist()):
        out.append(a * a + b * b - ((c * a * b) >> COEF_SHIFT))
    return [sum(out[3 * i:3 * i + 3]) for i in range(8)], int((xs * xs).sum())
