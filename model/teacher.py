#!/usr/bin/env python3
"""Teacher labels: run YOLO11n-pose on every recorded frame and mark 'face visible' (nose + at least one eye, conf >= 0.5).
Used to audit/clean the phase labels from record_faces.py. Writes teacher.json next to each session's summary.json.

  .venv/bin/python model/teacher.py data/face/<session>
"""
import glob
import json
import os
import sys

import cv2
import numpy as np
from ultralytics import YOLO

PHASES = ["face_front", "face_turned", "person_noface", "empty"]


def main():
    sess = sys.argv[1]
    model = YOLO(os.path.join(os.path.dirname(__file__), "..", "yolo11n-pose.pt"))
    out = {}
    for ph in PHASES:
        files = sorted(glob.glob(os.path.join(sess, ph, "*.jpg")))
        res = []
        for f in files:
            r = model.predict(cv2.imread(f), verbose=False, device=0, conf=0.25)[0]
            person, face, best = 0, False, 0.0
            if r.boxes is not None and len(r.boxes):
                person = len(r.boxes)
                kp = r.keypoints.conf.cpu().numpy() if r.keypoints is not None and r.keypoints.conf is not None else None
                if kp is not None:
                    for k in kp:
                        s = float(min(k[0], max(k[1], k[2])))
                        best = max(best, s)
                        if k[0] >= 0.5 and max(k[1], k[2]) >= 0.5:
                            face = True
            res.append(dict(file=os.path.basename(f), persons=person, face=face, face_score=round(best, 3)))
        out[ph] = res
    json.dump(out, open(os.path.join(sess, "teacher.json"), "w"))
    print(f"{'phase':<15}{'frames':>7}{'person':>8}{'face seen':>11}{'face %':>8}")
    for ph, res in out.items():
        n = len(res)
        print(f"{ph:<15}{n:>7}{sum(r['persons']>0 for r in res):>8}{sum(r['face'] for r in res):>11}{100*sum(r['face'] for r in res)/max(n,1):>7.0f}%")


if __name__ == "__main__":
    main()
