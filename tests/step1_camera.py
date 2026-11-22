#!/usr/bin/env python3
"""Step 1: main LVNext colour camera -> laptop CPU, lowest resolution, 30 fps, raw YUYV.

  python3 tests/step1_camera.py [--device 2] [--seconds 30]

Pass: mean fps >= 29.5, p99 frame interval < 50 ms, 0 failed/short reads, every frame 614,400 bytes.
"""
import argparse
import json
import os
import time

import cv2
import numpy as np

W, H, FPS = 640, 480, 30
EXPECT = W * H * 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--fourcc", default="YUYV", choices=["YUYV", "MJPG"])
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.device, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise SystemExit(f"FAIL: cannot open /dev/video{a.device} (is camera_viewer.py still running?)")
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*a.fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_FPS, FPS); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    fc = int(cap.get(cv2.CAP_PROP_FOURCC))
    got = (''.join(chr((fc >> 8 * k) & 255) for k in range(4)), int(cap.get(3)), int(cap.get(4)), cap.get(5))
    for _ in range(15):
        cap.read()                                     # let auto-exposure settle

    stamps, bad, sizes, motion_checksums = [], 0, set(), []
    t_end = time.perf_counter() + a.seconds
    cpu0 = time.process_time()
    while time.perf_counter() < t_end:
        ok, f = cap.read()
        t = time.perf_counter()
        if a.fourcc == "YUYV":
            good = ok and f is not None and f.nbytes == EXPECT
        else:                                          # MJPG with CONVERT_RGB=0 returns the raw JPEG bytes
            good = ok and f is not None and f.size > 1000 and bytes(f.ravel()[:2]) == b"\xff\xd8"
        if not good:
            bad += 1
            continue
        stamps.append(t); sizes.add(f.nbytes)
        if len(stamps) % 30 == 0:
            motion_checksums.append(int(f.ravel()[::97].astype(np.uint32).sum()))
    cpu = time.process_time() - cpu0
    cap.release()

    iv = np.diff(stamps) * 1000
    fps = (len(stamps) - 1) / (stamps[-1] - stamps[0])
    stuck = len(motion_checksums) > 3 and len(set(motion_checksums)) == 1
    res = dict(negotiated=dict(fourcc=got[0], width=got[1], height=got[2], fps=got[3]),
               frames=len(stamps), failed_reads=bad, frame_bytes=sorted(sizes),
               mean_fps=round(fps, 2), interval_ms=dict(p50=round(float(np.percentile(iv, 50)), 1),
                                                        p99=round(float(np.percentile(iv, 99)), 1),
                                                        max=round(float(iv.max()), 1)),
               frames_over_50ms=int((iv > 50).sum()), cpu_percent_of_one_core=round(100 * cpu / a.seconds, 1),
               image_changes_over_time=not stuck)
    checks = {
        "mean fps >= 29.5": fps >= 29.5,
        "p99 interval < 50 ms": res["interval_ms"]["p99"] < 50,
        "0 failed/short reads": bad == 0,
        (f"every frame {EXPECT} bytes" if a.fourcc == "YUYV" else "every frame is a valid JPEG"): (sizes == {EXPECT}) if a.fourcc == "YUYV" else len(sizes) > 0,
        f"negotiated {a.fourcc} 640x480": got[:3] == (a.fourcc, W, H),
        "image not frozen": not stuck,
    }
    print(json.dumps(res, indent=1))
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    out = os.path.join(os.path.dirname(__file__), "..", "docs", f"step1_result_{a.fourcc}.json")
    json.dump(dict(result=res, checks=checks), open(out, "w"), indent=1)
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
