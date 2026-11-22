"""Acceptance checks for the agent (needs the resident server: run the dashboard or call vlm_agent.start() first).
Run from the project root:  .venv/bin/python -m vlm_agent.tests.check_agent
"""
import json
import os
import shutil
import sys
import tempfile
import time

import cv2
import numpy as np

import vlm_agent
from vlm_agent import agent, server

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name, info, flush=True)


def make_chunk(frames, t0=1_800_000_000_000_000, step_us=250_000, kind="motion"):
    d = tempfile.mkdtemp(prefix="vlmchk_")
    fr = []
    for i, img in enumerate(frames):
        cv2.imwrite(f"{d}/f{i:03d}.jpg", img)
        fr.append(dict(frame_id=i, ts_us=t0 + i * step_us, file=f"f{i:03d}.jpg"))
    return d, dict(event_id=1, kind=kind, frames=fr)


def main():
    if not server.available():
        print("runtime/models not installed"); return 1
    server.start()
    for _ in range(180):
        if server.STATE["loaded"]:
            break
        time.sleep(1)
    check("server loaded", server.STATE["loaded"], server.STATE["state"])
    if not server.STATE["loaded"]:
        return 1
    import ultralytics
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
    bus = cv2.resize(cv2.imread(src), (640, 480))
    blank = np.full((480, 640, 3), 30, np.uint8)
    # 1. different pictures -> different descriptions
    d1, m1 = make_chunk([bus] * 4); r1 = agent.analyze_chunk(d1, m1, baseline={})
    d2, m2 = make_chunk([blank] * 4); r2 = agent.analyze_chunk(d2, m2, baseline={})
    check("completed + description (picture)", r1["status"] == "completed" and len(r1["summary"]) > 20, r1["summary"][:120])
    check("different input -> different text", r1["summary"] != r2["summary"], "| blank: " + r2["summary"][:100])
    # 2. 10 s chunk -> 3 windows, ordered timestamps in the coverage, synthesis used
    d3, m3 = make_chunk([bus if i % 2 else blank for i in range(40)], step_us=250_000); r3 = agent.analyze_chunk(d3, m3, baseline={})
    ts = r3["coverage"]["sampled_frame_timestamps_s"]
    check("3 windows, timestamps increasing", len(r3["timeline"]) == 3 and ts == sorted(ts), f"{len(r3['timeline'])} windows, ts={ts}")
    check("coverage + runtime measured", r3["coverage"]["missing_intervals_s"] == [] and r3["runtime"]["elapsed_seconds"] > 0,
          f"elapsed {r3['runtime']['elapsed_seconds']} s, peak GPU mem in use {r3['runtime']['peak_gpu_mem_used_mib']} MiB")
    # 3. empty / corrupt input -> clear failure
    d4, m4 = make_chunk([]); r4 = agent.analyze_chunk(d4, m4, baseline={})
    check("empty chunk -> failed with error", r4["status"] == "failed" and r4.get("error"), r4.get("error"))
    d5, m5 = make_chunk([bus]); open(f"{d5}/f000.jpg", "wb").write(b"not a jpeg"); r5 = agent.analyze_chunk(d5, m5, baseline={})
    check("corrupt frame -> failed, no invented text", r5["status"] == "failed" and not r5["summary"], r5.get("error"))
    # 4. no state leak: same input twice gives the same answer (temperature 0, stateless)
    r1b = agent.analyze_chunk(d1, m1, baseline={})
    check("stateless: repeat gives same text", r1b["summary"] == r1["summary"])
    # 5. context chunk updates the baseline; motion chunk request includes it
    dc, mc = make_chunk([blank] * 10, step_us=30_000, kind="context"); agent.BASELINE.update(text="", ts_us=0)
    rc = agent.analyze_chunk(dc, mc)
    check("context chunk stores baseline", bool(agent.BASELINE["text"]), agent.BASELINE["text"][:80])
    for d in (d1, d2, d3, d4, d5, dc):
        shutil.rmtree(d, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
