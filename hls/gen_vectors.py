#!/usr/bin/env python3
"""Generate bit-exact test vectors for the HLS testbenches from the golden models.

  .venv/bin/python hls/gen_vectors.py [--session data/sensors/<ts>]      (with --session, real recorded frames/audio are appended)
Writes hls/vectors/{rgb,ir}_frames.bin + _exp.txt and audio_blocks.bin + audio_exp.txt.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sensors"))
from golden import ChangeDetector, N_BLOCK, goertzel_bands_fast

rng = np.random.default_rng(42)


def synth_frames(h, w, n):
    base = rng.integers(60, 190, (h, w)).astype(np.int32)
    frames = []
    for i in range(n):
        y = base + rng.integers(-3, 4, (h, w))
        if i % 3 == 1:
            y[h // 4:h // 2, (i * 37) % (w // 2):(i * 37) % (w // 2) + w // 4] = 250
        if i == 5: y[:] = 255
        if i == 6: y[:] = 0
        if i == 7: y = rng.integers(0, 256, (h, w))
        frames.append(np.clip(y, 0, 255).astype(np.uint8))
    return frames


def write_change(name, frames, as_yuyv):
    cd = ChangeDetector()
    blob, lines = bytearray(), []
    for i, y in enumerate(frames):
        thr, sh = (24, 3) if i < 10 else (10, 2) if i < 14 else (40, 4)
        cd.pix_thresh, cd.bg_shift = thr, sh
        reset = 1 if i == 0 else 0
        changed, sum_cur = cd.step_raw(y, bool(reset))
        oh, ow = y.shape[0] // 5, y.shape[1] // 5
        lines.append(f"{thr} {sh} {reset} {changed} {sum_cur} {changed * 1000 // (ow * oh)} {i + 1}")
        if as_yuyv:
            f = np.empty((y.shape[0], y.shape[1], 2), np.uint8); f[..., 0] = y; f[..., 1] = 128 + (i % 7)
            blob += f.tobytes()
        else:
            blob += y.tobytes()
    open(f"{HERE}/vectors/{name}_frames.bin", "wb").write(bytes(blob))
    open(f"{HERE}/vectors/{name}_exp.txt", "w").write("\n".join(lines) + "\n")
    print(f"{name}: {len(frames)} frames; changed counts {[int(l.split()[3]) for l in lines]}")


# ---------------------------------------------------------------- image_change (full detector in the PL)
CROP_R0, CROP_R1, CROP_C0, CROP_C1 = 112, 368, 64, 576      # 512x256 centre crop of the 640x480 frame


def image_scene():
    yy, xx = np.mgrid[0:480, 0:640]
    return (90 + xx * 60 // 640 + yy * 40 // 480 + 20 * (((xx // 80) + (yy // 60)) % 2)).astype(np.int32)


def image_frame(base, rg, spec):
    if spec.get("random"):
        y = rg.integers(0, 256, base.shape)
    else:
        y = base + rg.integers(-2, 3, base.shape) + spec.get("delta", 0)
        if "block" in spec:
            r0, c0, h, w = spec["block"]; y[r0:r0 + h, c0:c0 + w] = spec.get("val", 250)
    return np.clip(y, 0, 255).astype(np.uint8)


def write_image_vectors(session):
    from image_detector import DetectorConfig, ImageChangeDetector, Preprocessor
    rg = np.random.default_rng(7)
    base = image_scene()
    pre = Preprocessor(256, 512, "gray")
    blk = lambda i, r, c: {"block": (r + 20 * i, c + 50 * i, 100, 200)}
    sched1 = ([{}] * 7 + [blk(i, 150, 100) for i in range(6)] + [{}] * 4 + [{"delta": 30}] * 3 + [{}] * 2 + [{"random": True}]
              + [{}] * 5 + [{"block": (200 + 10 * i, 300, 60, 80), "val": 200} for i in range(6)] + [{"delta": -25}] * 4 + [{}] * 6)
    sched2 = ([{}] * 5 + [blk(i, 120, 80) for i in range(6)] + [{}] * 3 + [{"delta": 40}] * 3 + [{"random": True}] + [{}] * 4
              + [{"delta": -35}] * 3 + [{}] * 5)
    sched4 = [{}] * 4 + [{"delta": 35}] * 4 + [{}] * 4
    default = DetectorConfig()
    variant = DetectorConfig(pix_thresh_min=15, var_init=6, var_min=2, var_max=100, var_shift=2, cell_fraction_num=1,
                             cell_fraction_den=3, min_cells=3, persist_frames=3, global_fraction_num=1, global_fraction_den=2,
                             illumination_min_offset=15, illumination_residual_num=1, illumination_residual_den=10, freeze_frames=2)
    noillum = DetectorConfig(illumination_enabled=False)
    seqs = [("synthetic default", default, [image_frame(base, rg, sp) for sp in sched1], {0, 28}),
            ("synthetic variant", variant, [image_frame(base, rg, sp) for sp in sched2], {0}),
            ("synthetic no-illumination", noillum, [image_frame(base, rg, sp) for sp in sched4], {0})]
    if session:
        rr = np.load(f"{session}/rgb_raw.npy")
        seqs.append(("real session", default, list(rr[::2][:30]), {0}))
    roi = np.ones((64, 64), bool)
    blob, lines, reasons = bytearray(), [], []
    for name, cfg, frames, resets in seqs:
        det = ImageChangeDetector(cfg, roi); count = 0
        # host-computed limits (see hls/image_change.cpp)
        cell_req = (64 * cfg.cell_fraction_num + cfg.cell_fraction_den - 1) // cfg.cell_fraction_den
        glim = 4096 * cfg.global_fraction_num // cfg.global_fraction_den
        rlim = 4096 * cfg.illumination_residual_num // cfg.illumination_residual_den
        params = [cfg.pix_thresh_min, cfg.var_init, cfg.var_min, cfg.var_max, cfg.var_shift, cfg.min_cells, cfg.persist_frames,
                  cfg.freeze_frames, int(cfg.illumination_enabled), cfg.illumination_min_offset, cell_req, glim, rlim]
        for i, y in enumerate(frames):
            reset = int(i in resets)
            if reset: det.reset(); count = 0
            res = det.update(pre(np.ascontiguousarray(y[CROP_R0:CROP_R1, CROP_C0:CROP_C1])))
            count += 1
            f = np.empty((480, 640, 2), np.uint8); f[..., 0] = y; f[..., 1] = 128 + (i % 7)
            blob += f[CROP_R0:CROP_R1].tobytes()
            vals = [int(res.fired), int(res.reason), res.score, int(res.region_pass), res.active_cells, res.changed_pixels,
                    res.persistence_count, count]
            lines.append(" ".join(str(v) for v in params + [reset] + vals + res.cell_counts.ravel().tolist()))
            reasons.append((name, res.reason.name))
    open(f"{HERE}/vectors/image_frames.bin", "wb").write(bytes(blob))
    open(f"{HERE}/vectors/image_exp.txt", "w").write("\n".join(lines) + "\n")
    from collections import Counter
    for name in dict.fromkeys(n for n, _ in reasons):
        print(f"image [{name}]:", dict(Counter(r for n, r in reasons if n == name)))
    print(f"image: {len(lines)} frames ({len(blob) // 1024} KiB)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--session", default="")
    a = ap.parse_args()
    os.makedirs(f"{HERE}/vectors", exist_ok=True)
    rgb = synth_frames(480, 640, 16); ir = synth_frames(480, 480, 16)
    blocks = []
    t = np.arange(N_BLOCK)
    blocks.append(np.zeros(N_BLOCK, np.int16))
    blocks.append((12000 * np.sin(2 * np.pi * 1000 / 16000 * t)).astype(np.int16))
    blocks.append((30000 * np.sign(np.sin(2 * np.pi * 250 / 16000 * t))).astype(np.int16))           # near full-scale square wave
    blocks.append(np.full(N_BLOCK, 32767, np.int16)); blocks.append(np.full(N_BLOCK, -32768, np.int16))
    blocks.append(((-1) ** t * 32767).astype(np.int16))                                              # Nyquist, full scale
    blocks += [rng.normal(0, 3000, N_BLOCK).clip(-32768, 32767).astype(np.int16) for _ in range(6)]
    if a.session:
        rr = np.load(f"{a.session}/rgb_raw.npy"); ii = np.load(f"{a.session}/ir_raw.npy")
        rgb += list(rr[:24]); ir += list(ii[:24])
        import wave
        w = wave.open(f"{a.session}/audio.wav"); x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        blocks += [x[s:s + N_BLOCK] for s in range(16000, len(x) - N_BLOCK, N_BLOCK * 40)][:40]
    write_change("rgb", rgb, True); write_change("ir", ir, False)
    ab, lines = bytearray(), []
    for i, b in enumerate(blocks):
        bands, ss = goertzel_bands_fast(b)
        lines.append(" ".join(str(v) for v in bands) + f" {ss} {i + 1}")
        ab += b.astype(np.int16).tobytes()
    open(f"{HERE}/vectors/audio_blocks.bin", "wb").write(bytes(ab))
    open(f"{HERE}/vectors/audio_exp.txt", "w").write("\n".join(lines) + "\n")
    print(f"audio: {len(blocks)} blocks")
    write_image_vectors(a.session)


if __name__ == "__main__":
    main()
