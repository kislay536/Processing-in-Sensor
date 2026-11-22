#!/usr/bin/env python3
"""Record N seconds from the camera at a low fps into an AVI (MJPG), for benchmarking. Stays local."""
import sys, time, cv2
dev, secs, fps, out = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
cap.set(3, 640); cap.set(4, 480); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 480))
t0, nxt, n = time.time(), time.time(), 0
while time.time() - t0 < secs:
    ok, f = cap.read()
    if not ok or time.time() < nxt: continue
    nxt += 1.0 / fps
    vw.write(cv2.resize(f, (640, 480))); n += 1
vw.release(); cap.release()
print(f"saved {n} frames to {out}")
