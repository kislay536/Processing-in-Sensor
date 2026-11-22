"""Cheap, model-free analysis: how much changed, when, and which frames are the keyframes."""
import os
import cv2
import numpy as np


def analyze(event_dir, meta, report):
    files = [os.path.join(event_dir, f["file"]) for f in meta["frames"]]
    grays = [cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY) for p in files]
    diffs = [0.0] + [float(np.mean(cv2.absdiff(a, b))) for a, b in zip(grays, grays[1:])]
    peak = int(np.argmax(diffs))
    trig = next((i for i, f in enumerate(meta["frames"]) if f["frame_id"] == meta["trigger_frame_id"]), 0)
    span = (meta["frames"][-1]["ts_us"] - meta["frames"][0]["ts_us"]) / 1e6
    report["keyframes"] = [meta["frames"][i]["file"] for i in sorted({0, trig, peak, len(files) - 1})]
    report["sections"]["Summary (model-free)"] = (
        f"Window of {len(files)} frames covering {span:.1f} s. Trigger at frame {meta['trigger_frame_id']} "
        f"(motion {meta['motion_x1000']/10:.1f}% of pixels). Largest inter-frame change at "
        f"{meta['frames'][peak]['file']}. Keyframes: {', '.join(report['keyframes'])}.")
    report["summary"] = f"{len(files)} frames, {span:.1f}s, peak change {diffs[peak]:.1f}"
