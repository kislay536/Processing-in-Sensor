#!/usr/bin/env python3
"""Trigger-parameter sweep. The GPU analyzer runs ONCE on every frame (cached); each gate setting then only
needs the CPU gate, because the analyzer is deterministic: a frame's result is the same whenever it is analysed.

  .venv/bin/python bench/sweep.py --video data/vid/vtest.avi --fps 5
"""
import argparse
import itertools
import json
import os
import sys

import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bench"))
from board_sim.detector import Params
from board_sim.gate import Gate
from run_bench import Analyzer, episodes, load_frames, to_yuyv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    a = ap.parse_args()
    cache = os.path.join(ROOT, "bench", f"flags_{os.path.basename(a.video)}_{a.fps}.json")
    src_fps = cv2.VideoCapture(a.video).get(cv2.CAP_PROP_FPS) or 30
    frames = load_frames(a.video, src_fps, a.fps)
    yuyv = [to_yuyv(f) for f in frames]
    if os.path.exists(cache):
        flags = json.load(open(cache))
    else:
        an = Analyzer("yolo11n-pose.pt")
        flags = [bool(an.person(f)) for f in frames]
        json.dump(flags, open(cache, "w"))
    truth = episodes(flags)
    print(f"{os.path.basename(a.video)}: {len(frames)} frames ({len(frames)/a.fps:.0f} s), "
          f"{sum(flags)} frames with a person, {len(truth)} person episodes\n")
    print(f"{'motion_t':>8} {'k':>2} {'n_pre':>5} {'n_post':>6} {'cool':>4} | {'frames->GPU':>11} {'%':>6} | {'episodes':>9} {'person frames':>14}")
    for mt, k, npre, npost, cool in itertools.product((15, 40), (2, 3), (5, 15, 50), (3, 10), (10,)):
        p = Params(motion_t=mt, k_consec=k, n_pre=npre, n_post=npost, cooldown=cool)
        g = Gate(p)
        sent = set()
        for i, y in enumerate(yuyv):
            _, ev = g.feed(i, i, y)
            if ev:
                sent.update(fid for fid, _, _ in ev["frames"])
        cov = sum(any(i in sent and flags[i] for i in range(s, e + 1)) for s, e in truth)
        pf = sum(1 for i in sent if flags[i])
        print(f"{mt:>8} {k:>2} {npre:>5} {npost:>6} {cool:>4} | {len(sent):>11} {100*len(sent)/len(frames):>5.1f}% | "
              f"{cov:>4}/{len(truth):<4} {pf:>6}/{sum(flags):<6}")


if __name__ == "__main__":
    main()
