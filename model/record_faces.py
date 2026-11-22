#!/usr/bin/env python3
"""Record labelled clips from the LVNext main camera for training the face detector (Step 2b).

  .venv/bin/python model/record_faces.py [--start-delay 12]

Phases are announced by voice (spd-say), a desktop notification and a bell. Frames are kept 1 of 5 (about 6 fps), exactly like the
board's input. For every kept frame it stores (a) the 128x96 gray image made by the SAME 5x5 box downscale the FPGA will use
(from the raw YUYV Y plane) in an .npz, and (b) a 320x240 JPEG for human review. Everything stays under data/face (local only).
"""
import argparse
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from board_sim.detector import downscale_5x5, y_plane

W, H = 640, 480
# (name, label, seconds, spoken instruction, label meaning)
PHASES = [
    ("face_front", 1, 50, "Look straight into the camera lens, not at the screen. Move slowly a bit closer and further, and tilt your head slightly.", "frontal face visible"),
    ("face_turned", 1, 40, "Keep looking toward the camera and turn your head slowly left and right, up and down. Part of your face stays visible.", "face partly turned but visible"),
    ("person_noface", 0, 40, "Stay in view but hide your face. Turn your back to the camera, or cover your whole face with both hands.", "person present, no face"),
    ("leave", None, 10, "Now leave completely. Walk out of the camera view and stay out.", ""),
    ("empty", 0, 30, "Stay out of the picture entirely. Do not touch the camera.", "empty room"),
]


def cue(text, bell=True):
    subprocess.Popen(["notify-send", "-t", "6000", "PiSe recording", text], stderr=subprocess.DEVNULL)
    subprocess.Popen(["spd-say", "-w", text], stderr=subprocess.DEVNULL)
    if bell:
        subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"], stderr=subprocess.DEVNULL)
    print(">>", text, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "face"))
    ap.add_argument("--start-delay", type=float, default=12)
    ap.add_argument("--keep-every", type=int, default=5)
    ap.add_argument("--session", default=time.strftime("%Y%m%d_%H%M%S"))
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.device, cv2.CAP_V4L2)
    if not cap.isOpened():
        sys.exit("cannot open camera (is the dashboard or another program using it?)")
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    for _ in range(20):
        cap.read()

    sess = os.path.join(a.out, a.session)
    os.makedirs(sess, exist_ok=True)
    cue(f"Recording starts in {int(a.start_delay)} seconds. Get in front of the camera.", bell=False)
    t_end = time.time() + a.start_delay
    while time.time() < t_end:                      # keep draining the camera so frames stay fresh
        cap.read()

    summary = []
    for name, label, secs, say, meaning in PHASES:
        cue(f"{name.replace('_', ' ')}. {say}")
        pdir = os.path.join(sess, name)
        os.makedirs(pdir, exist_ok=True)
        grays, jpgs, k, t_start = [], 0, 0, time.time()
        settle = 3.0                                 # give the person a moment to change pose; these frames are discarded
        while time.time() - t_start < secs:
            ok, f = cap.read()
            if not ok or f is None or f.nbytes != W * H * 2:
                continue
            if label is None or time.time() - t_start < settle:
                continue
            if k % a.keep_every == 0:
                yuyv = f.tobytes()
                grays.append(downscale_5x5(y_plane(yuyv)))
                bgr = cv2.cvtColor(f.reshape(H, W, 2), cv2.COLOR_YUV2BGR_YUY2)
                cv2.imwrite(os.path.join(pdir, f"{len(grays)-1:04d}.jpg"), cv2.resize(bgr, (320, 240)), [cv2.IMWRITE_JPEG_QUALITY, 88])
                jpgs += 1
            k += 1
        if label is not None:
            np.savez_compressed(os.path.join(pdir, "gray128x96.npz"), x=np.stack(grays), label=label)
            summary.append(dict(phase=name, label=label, meaning=meaning, frames=len(grays), seconds=secs - settle))
            print(f"   {name}: {len(grays)} frames", flush=True)
    json.dump(dict(session=a.session, keep_every=a.keep_every, phases=summary), open(os.path.join(sess, "summary.json"), "w"), indent=1)
    cue("Recording finished. Thank you.")
    print("saved to", sess, flush=True)


if __name__ == "__main__":
    main()
