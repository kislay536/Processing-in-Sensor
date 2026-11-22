"""Golden model of the board-side detector (integer arithmetic, mirrors what the PL will do).

Pipeline per frame:
  YUYV 640x480 -> take Y (every other byte) -> 5x5 box average (integer) -> 128x96 gray
  motion gate: |cur - bg| > PIX_THRESH  -> changed-pixel fraction (x1000)
  background:  bg16 += (cur*16 - bg16) >> BG_SHIFT   (fixed point, 4 fractional bits)
Trigger rule (PS side): motion_x1000 > MOTION_T for K consecutive frames (after warm-up, outside cooldown),
optionally AND person_x1000 > PERSON_T when a person classifier is attached.
"""
from dataclasses import dataclass, field
import numpy as np

W_IN, H_IN = 640, 480
W_S, H_S = 128, 96  # downscaled size, box 5x5


def y_plane(yuyv: bytes, w=W_IN, h=H_IN) -> np.ndarray:
    return np.frombuffer(yuyv, dtype=np.uint8).reshape(h, w * 2)[:, ::2]


def downscale_5x5(y: np.ndarray) -> np.ndarray:
    h, w = y.shape
    assert (h, w) == (H_IN, W_IN)
    s = y.astype(np.uint32).reshape(H_S, 5, W_S, 5).sum(axis=(1, 3))
    return (s // 25).astype(np.uint8)


@dataclass
class Params:
    pix_thresh: int = 24
    bg_shift: int = 3
    motion_t: int = 15        # per-mille of changed pixels
    k_consec: int = 2
    warmup: int = 25          # camera auto-exposure settles in the first seconds; ignore them
    cooldown: int = 25
    person_t: int = 0         # 0 = motion-only mode
    n_pre: int = 50
    n_post: int = 10


@dataclass
class Detector:
    p: Params = field(default_factory=Params)
    bg16: np.ndarray = None
    seen: int = 0
    consec: int = 0
    cool: int = 0

    def step(self, yuyv: bytes, person_x1000: int = 0):
        """Returns (motion_x1000, fire: bool)."""
        small = downscale_5x5(y_plane(yuyv)).astype(np.int32)
        if self.bg16 is None:
            self.bg16 = small * 16
        diff = np.abs(small - (self.bg16 >> 4))
        changed = int((diff > self.p.pix_thresh).sum())
        motion = changed * 1000 // (W_S * H_S)
        self.bg16 = self.bg16 + ((small * 16 - self.bg16) >> self.p.bg_shift)
        self.seen += 1
        fire = False
        if self.cool > 0:
            self.cool -= 1
            self.consec = 0
        elif self.seen > self.p.warmup:
            ok = motion > self.p.motion_t and (self.p.person_t == 0 or person_x1000 > self.p.person_t)
            self.consec = self.consec + 1 if ok else 0
            if self.consec >= self.p.k_consec:
                fire = True
                self.consec = 0
                self.cool = self.p.cooldown
        return motion, fire
