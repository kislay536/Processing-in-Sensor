#!/usr/bin/env python3
"""Run the three golden detectors over a multi-sensor recording and report per-phase score distributions.
  .venv/bin/python sensors/analyze.py data/sensors/<session>
"""
import json
import sys
import wave

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from golden import N_BLOCK, BAND_HZ, ChangeDetector, goertzel_bands_fast

sess = sys.argv[1]
phases = json.load(open(f"{sess}/phases.json"))


def phase_of(t):
    for p in phases:
        if p["cue_end"] <= t < p["end"]:
            return p["name"]
    return None


def series_change(small, ts, thr, shift):
    cd = ChangeDetector(pix_thresh=thr, bg_shift=shift)
    n = small.shape[1] * small.shape[2]
    out = []
    for i, f in enumerate(small):
        ch, sm = cd.step(f, reset=(i == 0))
        out.append(1000 * ch // n)
    return np.array(out)


def summarize(name, score, ts, positives):
    print(f"\n{name}")
    print(f"  {'phase':<13}{'n':>5}{'median':>8}{'p90':>7}{'p99':>7}{'max':>7}")
    for p in phases:
        m = np.array([phase_of(t) == p["name"] for t in ts])
        s = score[m]
        print(f"  {p['name']:<13}{len(s):>5}{np.median(s):>8.1f}{np.percentile(s, 90):>7.1f}{np.percentile(s, 99):>7.1f}{s.max():>7.1f}")
    neg = np.array([phase_of(t) in ("quiet", "quiet2") for t in ts]); pos = np.array([phase_of(t) in positives for t in ts])
    print(f"  rule check (score > T for 2 consecutive samples): quiet false-trigger / target-phase detection")
    for T in sorted(set(np.percentile(score[pos | neg], [50, 70, 80, 90, 95]).round(1))):
        hit = (score > T)
        two = hit[1:] & hit[:-1]
        fa = two[neg[1:] & neg[:-1]].mean() if (neg[1:] & neg[:-1]).any() else 0
        tp = two[pos[1:] & pos[:-1]].mean() if (pos[1:] & pos[:-1]).any() else 0
        print(f"    T={T:>7}: false-positive rate {100*fa:5.1f}%   detection rate {100*tp:5.1f}%")


rgb = np.load(f"{sess}/rgb_y128x96.npy"); rts = np.load(f"{sess}/rgb_ts.npy")
ir = np.load(f"{sess}/ir_y96x96.npy"); its = np.load(f"{sess}/ir_ts.npy")
print(f"rgb frames {len(rgb)} ({len(rgb)/(rts[-1]-rts[0]):.1f}/s), ir frames {len(ir)} ({len(ir)/(its[-1]-its[0]):.1f}/s)")
summarize("COLOUR camera: changed pixels per mille (pix_thresh 24, shift 3)", series_change(rgb, rts, 24, 3), rts, ("motion_only", "both"))
summarize("IR camera: changed pixels per mille (pix_thresh 24, shift 3)", series_change(ir, its, 24, 3), its, ("motion_only", "both"))
summarize("IR camera: changed pixels per mille (pix_thresh 12, shift 3)", series_change(ir, its, 12, 3), its, ("motion_only", "both"))

w = wave.open(f"{sess}/audio.wav"); x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
t0 = json.load(open(f"{sess}/audio_t0.json"))["t0"]
nb = len(x) // N_BLOCK
P = np.array([goertzel_bands_fast(x[i * N_BLOCK:(i + 1) * N_BLOCK])[0] for i in range(nb)], dtype=np.float64)   # (blocks, 8)
bts = t0 + (np.arange(nb) + 0.5) * N_BLOCK / 16000
base = np.zeros_like(P); b = P[:50].mean(0)
for i in range(nb):
    base[i] = b
    b = b + (P[i] - b) / 64                                   # baseline = EMA over ~2 s
ratio_db = 10 * np.log10((P + 1) / (base + 1))
summarize("MICROPHONE: max over 8 bands of (power / baseline) in dB", ratio_db.max(1), bts, ("sound_only", "both"))
print("\nmedian band power per phase (10*log10), bands Hz:", BAND_HZ)
for p in phases:
    m = np.array([phase_of(t) == p["name"] for t in bts])
    print(f"  {p['name']:<13}", np.round(10 * np.log10(np.median(P[m], 0) + 1), 0).astype(int).tolist())
