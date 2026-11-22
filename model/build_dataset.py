#!/usr/bin/env python3
"""Build the distillation dataset: 128x96 gray frames (the FPGA's input format) + the YuNet face score for each frame.

  .venv/bin/python model/build_dataset.py

Sources: the two recorded sessions (gray npz saved by record_faces.py; YuNet runs on the saved 320x240 JPEG), and two videos
(resized to 640x480, gray, same 5x5 box downscale as the board; YuNet runs on the 320x240 colour frame).
Label = max YuNet face score in the frame (0 if no face found at score>=0.3). The label comes from a model, not a human.
"""
import glob
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from board_sim.detector import downscale_5x5

yunet = cv2.FaceDetectorYN.create(os.path.join(ROOT, "model/pretrained/yunet.onnx"), "", (320, 240), score_threshold=0.3, nms_threshold=0.3, top_k=10)


MIN_W = 32      # face box width at 320x240 (= 16 px at the 128x96 network input, = 80 px at 640x480): smaller faces are not resolvable


def face_score(bgr320):
    """Returns (best score among faces >= MIN_W wide, best score among faces of any size)."""
    _, faces = yunet.detect(bgr320)
    if faces is None or not len(faces):
        return 0.0, 0.0
    big = faces[faces[:, 2] >= MIN_W]
    return (float(big[:, 14].max()) if len(big) else 0.0), float(faces[:, 14].max())


def session(sess):
    xs, sc, src = [], [], []
    for ph in ("face_front", "face_turned", "person_noface", "empty"):
        d = os.path.join(ROOT, "data/face", sess, ph)
        x = np.load(os.path.join(d, "gray128x96.npz"))["x"]
        jpgs = sorted(glob.glob(os.path.join(d, "*.jpg")))
        assert len(jpgs) == len(x), (d, len(jpgs), len(x))
        for i, p in enumerate(jpgs):
            xs.append(x[i]); sc.append(face_score(cv2.imread(p))); src.append(f"{sess}/{ph}")
    return xs, sc, src


def video(path, name, step):
    cap = cv2.VideoCapture(os.path.join(ROOT, path))
    xs, sc, src, i = [], [], [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            f640 = cv2.resize(f, (640, 480))
            y = cv2.cvtColor(f640, cv2.COLOR_BGR2GRAY)
            xs.append(downscale_5x5(y)); sc.append(face_score(cv2.resize(f640, (320, 240)))); src.append(name)
        i += 1
    return xs, sc, src


def main():
    X, S, A, G = [], [], [], []
    for name, fn in (("s2_good_angle", lambda: session("20261121_185652")), ("s1_tilted", lambda: session("20261121_184429")),
                     ("room_video", lambda: video("data/rec/room_150s.avi", "room_video", 1)),
                     ("vtest_video", lambda: video("data/vid/vtest.avi", "vtest_video", 2))):
        xs, sc, src = fn()
        X += xs; S += [b for b, _ in sc]; A += [a for _, a in sc]
        G += [name] * len(xs)
        big, anyf = np.array([b for b, _ in sc]), np.array([a for _, a in sc])
        print(f"{name:<15} {len(xs):>5} frames: face {int((big >= 0.6).sum()):>4} | no face {int((anyf < 0.3).sum()):>4} | uncertain (small/weak) {int(((big < 0.6) & (anyf >= 0.3)).sum()):>4}", flush=True)
    np.savez_compressed(os.path.join(ROOT, "data/face/dataset.npz"), x=np.stack(X), score=np.array(S, np.float32), score_any=np.array(A, np.float32), group=np.array(G))
    print("saved data/face/dataset.npz", len(X))


if __name__ == "__main__":
    main()
