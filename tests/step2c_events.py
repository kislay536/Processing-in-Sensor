#!/usr/bin/env python3
"""Step 2c end-to-end test on the real board: synthetic scene -> relay -> board (PL image-change IP) -> motion-gated stream -> GPU assembler.

  .venv/bin/python tests/step2c_events.py [--board 192.168.7.2]
Needs the board running board/fw_build/eventcam.elf with the image_change bitstream; stop the dashboard first (single board connection).
Scenario A: a block moves from t=12 s to t=16 s in a 40 s run  -> exactly 1 chunk (motion ended), frames only around the motion, timestamps monotonic.
Scenario B: the block moves from t=10 s to t=26 s with max_chunk_s=3 -> several consecutive chunks, each <= ~3 s, none lost between them.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
ap = argparse.ArgumentParser(); ap.add_argument("--board", default="192.168.7.2")
a = ap.parse_args()


def run(name, seconds, motion_at, motion_dur, cfg):
    out = os.path.join(ROOT, "tests", "_step2c_" + name)
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    recv = subprocess.Popen([PY, f"{ROOT}/gpu/receiver.py", "--board", a.board, "--out", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    cmd = [PY, f"{ROOT}/relay/relay.py", "--board", a.board, "--source", "synthetic", "--seconds", str(seconds), "--keep-every", "5",
           "--motion-at", str(motion_at), "--motion-dur", str(motion_dur), "--period", "100"] + (["--cfg"] + cfg if cfg else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    time.sleep(5)
    recv.terminate(); recv.wait()
    metas = [json.load(open(f"{out}/{d}/meta.json")) for d in sorted(os.listdir(out)) if d.startswith("event_") and os.path.exists(f"{out}/{d}/meta.json")]
    print(f"[{name}] {r.stdout.strip().splitlines()[-1]}")
    for m in metas:
        print(f"   chunk {m['event_id']}: episode {m['episode']} part {m['chunk']}, {m['n_frames']} frames, {m['duration_s']} s @ {m['fps']} fps, ended: {m['end_reason']}")
    return metas


ok = True
A = run("A", 40, 12, 4, ["ctx_period_s=0"])   # context bursts off: this scenario checks the motion path only
total = sum(m["n_frames"] for m in A)
mono = all(all(f1["ts_us"] < f2["ts_us"] for f1, f2 in zip(m["frames"], m["frames"][1:])) for m in A)
passA = len(A) == 1 and A[0]["end_reason"] == "motion ended" and 20 <= total <= 50 and mono
print(f"   A: {len(A)} chunk(s), {total} frames streamed of 241 sent to the board, timestamps monotonic={mono} -> {'PASS' if passA else 'FAIL'}")
B = run("B", 40, 10, 16, ["max_chunk_s=3", "ctx_period_s=0"])
gaps = [m2["frames"][0]["frame_id"] - m1["frames"][-1]["frame_id"] for m1, m2 in zip(B, B[1:]) if m1["episode"] == m2["episode"]]
passB = len(B) >= 4 and all(m["duration_s"] <= 3.6 for m in B) and all(g == 1 for g in gaps) and B[0]["end_reason"] == "max chunk length"
print(f"   B: {len(B)} chunks, max duration {max((m['duration_s'] for m in B), default=0)} s, frame-id step between consecutive chunks {gaps} -> {'PASS' if passB else 'FAIL'}")
# Scenario C: static scene, context every 10 s, 10 frames each -> a baseline burst at connect, then one every ~10 s
C = run("C", 35, 999, 1, ["ctx_period_s=10", "ctx_frames=10"])
passC = len(C) >= 3 and all(m.get("kind") == "context" and m["n_frames"] == 10 and m["end_reason"] == "scene context" for m in C)
print(f"   C: {len(C)} context chunk(s) in 35 s, frames each {[m['n_frames'] for m in C]} -> {'PASS' if passC else 'FAIL'}")
# Scenario D: motion 12-20 s inside a 45 s run with the same context settings -> motion frames count towards the 10-frame minimum, so
# the 10-20 s window gets no extra burst (contexts at ~0, 10, 30, 40 s rather than also at 20 s)
D = run("D", 45, 12, 8, ["ctx_period_s=10", "ctx_frames=10"])
mot = [m for m in D if m.get("kind") == "motion"]; ctx = [m for m in D if m.get("kind") == "context"]
starts = sorted(m["start_ts_us"] for m in D)
passD = len(mot) == 1 and 3 <= len(ctx) <= 4 and all(m["n_frames"] == 10 for m in ctx)
print(f"   D: {len(mot)} motion chunk(s), {len(ctx)} context chunk(s) -> {'PASS' if passD else 'FAIL'}")
subprocess.run([PY, f"{ROOT}/relay/relay.py", "--board", a.board, "--source", "synthetic", "--seconds", "1", "--cfg", "max_chunk_s=30"], capture_output=True)   # restore default parameters (all others default too)
print("PASS" if passA and passB else "FAIL")
sys.exit(0 if passA and passB else 1)
