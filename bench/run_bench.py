#!/usr/bin/env python3
"""Gated vs continuous benchmark.

  .venv/bin/python bench/run_bench.py --video data/vid/vtest.avi --fps 5 [--realtime]

Same stream, same analyzer (YOLO11n-pose on the GPU, batch 1 like a live stream):
  CONTINUOUS : every frame goes to the GPU.
  GATED      : the CPU gate (same code the board runs) decides; only triggered windows go to the GPU.
Reports frames, GPU busy time, duty cycle, mean GPU power, bytes moved, and whether the gate missed
person episodes that the continuous run found.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from board_sim.detector import Params
from board_sim.gate import Gate

W, H = 640, 480


def load_frames(path, src_fps, target_fps):
    """Frames resized to 640x480 as a camera would deliver, subsampled to target_fps."""
    cap = cv2.VideoCapture(path)
    step = max(1, round(src_fps / target_fps))
    frames, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            frames.append(cv2.resize(f, (W, H)))
        i += 1
    return frames


def to_yuyv(bgr):
    y = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    f = np.empty((H, W, 2), np.uint8); f[..., 0] = y; f[..., 1] = 128
    return f.tobytes()


class PowerSampler:
    def __init__(self):
        self.samples, self.proc = [], None

    def __enter__(self):
        self.proc = subprocess.Popen(["nvidia-smi", "-lms", "100", "--query-gpu=power.draw,utilization.gpu",
                                      "--format=csv,noheader,nounits"], stdout=subprocess.PIPE, text=True)
        self.t = threading.Thread(target=self._read, daemon=True); self.t.start()
        return self

    def _read(self):
        for line in self.proc.stdout:
            try:
                p, u = (float(x) for x in line.split(","))
                self.samples.append((p, u))
            except ValueError:
                pass

    def __exit__(self, *a):
        self.proc.terminate()

    def mean_power(self):
        return float(np.mean([s[0] for s in self.samples])) if self.samples else float("nan")

    def mean_util(self):
        return float(np.mean([s[1] for s in self.samples])) if self.samples else float("nan")


class Analyzer:
    def __init__(self, weights):
        import torch
        from ultralytics import YOLO
        self.torch = torch
        self.model = YOLO(weights)
        self.model.predict(np.zeros((H, W, 3), np.uint8), verbose=False, device=0)   # warm-up
        self.busy = 0.0
        self.calls = 0

    def person(self, bgr):
        t0 = time.perf_counter()
        r = self.model.predict(bgr, verbose=False, device=0, conf=0.35, classes=[0])[0]
        self.torch.cuda.synchronize()
        self.busy += time.perf_counter() - t0
        self.calls += 1
        return len(r.boxes) > 0


def episodes(flags, gap=3, min_len=2):
    """Group frame indices flagged True into episodes (gaps <= gap frames are bridged)."""
    eps, start, last = [], None, None
    for i, f in enumerate(flags):
        if not f:
            continue
        if start is None:
            start = last = i
        elif i - last <= gap + 1:
            last = i
        else:
            eps.append((start, last)); start = last = i
    if start is not None:
        eps.append((start, last))
    return [e for e in eps if e[1] - e[0] + 1 >= min_len]


def run_stream(frames, analyzer, fps, gated, params, realtime):
    """Returns dict of metrics and per-frame detection flags (None where the GPU never saw the frame)."""
    n = len(frames)
    flags = [None] * n
    gate = Gate(params) if gated else None
    analyzer.busy, analyzer.calls = 0.0, 0
    sent_frames, bytes_to_gpu, events = 0, 0, 0
    t_start = time.perf_counter()
    with PowerSampler() as ps:
        time.sleep(0.4)
        t_run = time.perf_counter()
        for i, f in enumerate(frames):
            if realtime:
                target = t_run + i / fps
                while time.perf_counter() < target:
                    time.sleep(0.002)
            if not gated:
                flags[i] = analyzer.person(f)
                sent_frames += 1
                bytes_to_gpu += f.nbytes
            else:
                _, ev = gate.feed(i, i, to_yuyv(f))
                if ev:
                    events += 1
                    for fid, _, _ in ev["frames"]:
                        if flags[fid] is None:             # frames already analysed in an overlapping window are not re-sent
                            flags[fid] = analyzer.person(frames[fid])
                            sent_frames += 1
                            bytes_to_gpu += W * H * 2
        wall = time.perf_counter() - t_run
        time.sleep(0.3)
    return dict(frames_total=n, frames_to_gpu=sent_frames, events=events, gpu_busy_s=round(analyzer.busy, 3),
                stream_s=round(n / fps, 1), duty_pct=round(100 * analyzer.busy / (n / fps), 2),
                mean_power_w=round(ps.mean_power(), 1), mean_util_pct=round(ps.mean_util(), 1),
                mb_to_gpu=round(bytes_to_gpu / 1e6, 1), wall_s=round(wall, 1)), flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(ROOT, "data/vid/vtest.avi"))
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--weights", default="yolo11n-pose.pt")
    ap.add_argument("--realtime", action="store_true", help="pace frames in real time (for power numbers)")
    ap.add_argument("--motion-t", type=int, default=None)
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--n-pre", type=int, default=None)
    ap.add_argument("--n-post", type=int, default=None)
    ap.add_argument("--warmup", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "bench/results.json"))
    a = ap.parse_args()

    src_fps = cv2.VideoCapture(a.video).get(cv2.CAP_PROP_FPS) or 30
    frames = load_frames(a.video, src_fps, a.fps)
    print(f"{os.path.basename(a.video)}: {len(frames)} frames at {a.fps} fps ({len(frames)/a.fps:.0f} s of stream)", flush=True)

    p = Params()
    for name, val in (("motion_t", a.motion_t), ("k_consec", a.k), ("n_pre", a.n_pre), ("n_post", a.n_post), ("warmup", a.warmup)):
        if val is not None:
            setattr(p, name, val)

    an = Analyzer(a.weights)
    base, base_flags = run_stream(frames, an, a.fps, False, p, a.realtime)
    gate, gate_flags = run_stream(frames, an, a.fps, True, p, a.realtime)

    truth = episodes([bool(f) for f in base_flags])
    covered = sum(any(gate_flags[i] for i in range(s, e + 1)) for s, e in truth)
    frames_with_person = sum(bool(f) for f in base_flags)
    found_frames = sum(bool(g) and bool(b) for g, b in zip(gate_flags, base_flags))
    res = dict(params=p.__dict__, continuous=base, gated=gate,
               person_episodes=len(truth), episodes_caught_by_gated=covered,
               person_frames=frames_with_person, person_frames_seen_by_gated=found_frames)
    json.dump(res, open(a.out, "w"), indent=1)

    def row(k, label, fmt="{}"):
        print(f"  {label:<32}{fmt.format(base[k]):>14}{fmt.format(gate[k]):>14}")
    print(f"\n  {'':<32}{'CONTINUOUS':>14}{'GATED':>14}")
    row("frames_to_gpu", "frames sent to GPU")
    row("mb_to_gpu", "data sent to GPU (MB)")
    row("gpu_busy_s", "GPU busy time (s)")
    row("duty_pct", "GPU duty cycle (%)")
    if a.realtime:
        row("mean_power_w", "mean GPU power (W)")
        row("mean_util_pct", "mean GPU util (%)")
    print(f"\n  GPU frames: {100*gate['frames_to_gpu']/max(1,base['frames_to_gpu']):.1f}% of continuous | "
          f"events: {gate['events']}")
    print(f"  person episodes found by continuous run: {len(truth)}; also covered by gated run: {covered}")
    print(f"  frames with a person: {frames_with_person}; of those the gated run analysed+detected: {found_frames}")


if __name__ == "__main__":
    main()
