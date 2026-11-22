#!/usr/bin/env python3
"""GPU stage: connects to the board, receives event windows, saves them, runs the analyzer cascade.

  python3 gpu/receiver.py --board 192.168.7.2 --out events
"""
import argparse
import json
import os
import socket
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import proto
from gpu.analyzers import run_cascade
from gpu.chunks import ChunkAssembler


def save_event(out_root, ev):
    d = os.path.join(out_root, f"event_{ev['event_id']:04d}")
    os.makedirs(d, exist_ok=True)
    w, h = ev["w"], ev["h"]
    paths = []
    for fid, ts, payload in ev["frames"]:
        yuyv = np.frombuffer(payload, np.uint8).reshape(h, w, 2)
        bgr = cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUY2)
        p = os.path.join(d, f"f{fid:06d}.jpg")
        cv2.imwrite(p, bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        paths.append((fid, ts, p))
    meta = dict(event_id=ev["event_id"], trigger_frame_id=ev["trigger_frame_id"],
                motion_x1000=ev["motion_x1000"], person_x1000=ev["person_x1000"],
                n_frames=len(paths), frames=[dict(frame_id=f, ts_us=t, file=os.path.basename(p)) for f, t, p in paths],
                bytes_received=sum(len(f[2]) for f in ev["frames"]), received_at=time.time())
    with open(os.path.join(d, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    return d, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=proto.PORT_EVENTS)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "events"))
    ap.add_argument("--max-events", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    while True:
        try:
            s = socket.create_connection((a.board, a.port), timeout=5)
            break
        except OSError as e:
            print("waiting for board...", e, flush=True); time.sleep(1)
    s.settimeout(None)
    print(f"GPU stage connected to {a.board}:{a.port}", flush=True)
    n_ev = 0
    asm = ChunkAssembler(a.out)
    while True:
        kind, m = proto.read_message(s)
        if kind == "STA":
            with open(os.path.join(a.out, "stats.json"), "w") as fh:
                json.dump(dict(m, updated=time.time()), fh)
            continue
        if kind == "EVF":
            asm.on_frame(m)
            continue
        if kind == "EVA":
            asm.on_audio(m)
            continue
        t0 = time.time()
        if kind == "EVE":
            res = asm.on_end(m)
            if not res:
                continue
            d, meta = res
        else:                                              # legacy EVT1 window
            d, meta = save_event(a.out, m)
        print(f"chunk {meta['event_id']}: {meta['n_frames']} frames, {meta.get('duration_s', 0)} s, {meta['bytes_received']/1e6:.1f} MB -> {d}", flush=True)
        report = run_cascade(d, meta)
        report["analysis_seconds"] = round(time.time() - t0, 3)
        with open(os.path.join(d, "report.json"), "w") as fh:
            json.dump(report, fh, indent=1)
        with open(os.path.join(d, "report.md"), "w") as fh:
            fh.write(report["markdown"])
        print(f"  report: {report['summary']}", flush=True)
        n_ev += 1
        if a.max_events and n_ev >= a.max_events:
            break

if __name__ == "__main__":
    main()
