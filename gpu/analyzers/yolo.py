"""Small local detector (YOLO11n-pose, ~6 MB, runs on the laptop GPU): who/what is in the chunk and what they do.

Per frame: persons with 17 keypoints. Per chunk: person count, posture (standing / sitting / lying) from keypoints,
activity from how far the keypoints and the box centre travel between frames (still / moving / waving / walking).
Writes annotated keyframes det_*.jpg into the event dir and report['detections'].
"""
import os
import threading
import time
import cv2
import numpy as np

_WEIGHTS = os.path.join(os.path.dirname(__file__), "..", "..", "yolo11n-pose.pt")
_model = None
MAX_FRAMES = 40   # sample at most this many frames per chunk


STATE = dict(loaded=False, busy=False, analyzed=0, last_s=0.0, last_at=0.0, device="", error="")
_lock = threading.Lock()


def _get():
    global _model
    with _lock:
        if _model is None:
            from ultralytics import YOLO
            _model = YOLO(os.path.abspath(_WEIGHTS))
        return _model


def preload():
    """Load the weights onto the GPU and run one dummy inference so the first real chunk is not slowed by CUDA start-up. Model then stays resident."""
    try:
        m = _get()
        m.predict(np.zeros((480, 640, 3), np.uint8), verbose=False, imgsz=640)
        STATE.update(loaded=True, device=str(getattr(m.predictor, "device", "?")) + " (" + __import__("torch").cuda.get_device_name(0) + ")", error="")
    except Exception as e:
        STATE["error"] = repr(e)


def _timeline(per, t0):
    """Merge consecutive samples with the same (people, posture) into [start_s, end_s, text] segments."""
    def desc(p):
        if not p["n"]:
            return "no person"
        post = max(set(p["postures"]), key=p["postures"].count)
        return f"{p['n']} person{'s' if p['n'] > 1 else ''} {post}"
    segs = []
    for p in per:
        t, d = (p["ts_us"] - t0) / 1e6, desc(p)
        if segs and segs[-1][2] == d:
            segs[-1][1] = t
        else:
            segs.append([t, t, d])
    return [dict(start_s=round(a, 2), end_s=round(b, 2), text=d) for a, b, d in segs]


def _posture(kp, box):
    """kp: 17x3 (x, y, conf). Returns standing / sitting / lying / unknown."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if w > 1.2 * h:
        return "lying"
    ok = lambda i: kp[i, 2] > 0.4
    if ok(5) and ok(6) and ok(11) and ok(12) and ok(13) and ok(14):
        sh, hip, knee = (kp[5, 1] + kp[6, 1]) / 2, (kp[11, 1] + kp[12, 1]) / 2, (kp[13, 1] + kp[14, 1]) / 2
        torso = max(hip - sh, 1.0)
        return "standing" if (knee - hip) > 0.8 * torso else "sitting"
    return "standing" if h > 1.6 * w else "unknown"


def analyze(event_dir, meta, report):
    STATE["busy"] = True
    t_start = time.time()
    try:
        _analyze(event_dir, meta, report)
    finally:
        STATE.update(busy=False, loaded=True, analyzed=STATE["analyzed"] + 1, last_s=round(time.time() - t_start, 2), last_at=time.time())


def _analyze(event_dir, meta, report):
    frames = meta["frames"]
    step = max(1, len(frames) // MAX_FRAMES)
    sel = frames[::step]
    model = _get()
    per, track = [], []
    best, best_i = -1, 0
    imgs = []
    for f in sel:
        img = cv2.imread(os.path.join(event_dir, f["file"]))
        r = model.predict(img, verbose=False, conf=0.4, imgsz=640)[0]
        people = []
        if r.boxes is not None and len(r.boxes):
            boxes = r.boxes.xyxy.cpu().numpy()
            kps = r.keypoints.data.cpu().numpy()
            H, W = img.shape[:2]
            for b, k in zip(boxes, kps):
                # reject junk: box filling the frame (camera covered / close-up) or too few confident keypoints
                if (b[2] - b[0]) * (b[3] - b[1]) > 0.85 * W * H or int((k[:, 2] > 0.5).sum()) < 5:
                    continue
                people.append(dict(box=b.tolist(), post=_posture(k, b), kp=k))
        n = len(people)
        per.append(dict(file=f["file"], ts_us=f["ts_us"], n=n, postures=[p["post"] for p in people]))
        if people:
            big = max(people, key=lambda p: (p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]))
            track.append((f["ts_us"], np.array(big["box"]), big["kp"]))
        imgs.append((img, r, n))
        if n > best:
            best, best_i = n, len(imgs) - 1
    # activity of the main person: keypoint travel per second relative to body height
    act, speeds = "no person", []
    if len(track) >= 2:
        for (t0, b0, k0), (t1, b1, k1) in zip(track, track[1:]):
            dt = max((t1 - t0) / 1e6, 1e-3)
            hgt = max(b1[3] - b1[1], 1.0)
            c0, c1 = (b0[:2] + b0[2:]) / 2, (b1[:2] + b1[2:]) / 2
            walk = np.linalg.norm(c1 - c0) / hgt / dt            # body heights / s
            both = (k0[:, 2] > 0.4) & (k1[:, 2] > 0.4)
            limb = float(np.mean(np.linalg.norm(k1[both, :2] - k0[both, :2] - (c1 - c0), axis=1))) / hgt / dt if both.any() else 0.0
            speeds.append((walk, limb))
        walk = float(np.median([s[0] for s in speeds]))
        limb = float(np.median([s[1] for s in speeds]))
        act = "walking/moving across the view" if walk > 0.35 else ("moving in place (arms/body)" if limb > 0.35 else "mostly still")
    elif len(track) == 1:
        act = "briefly visible"
    # annotated keyframes: start, most people, middle, end
    idx = sorted({0, best_i, len(imgs) // 2, len(imgs) - 1})
    keys = []
    for i in idx:
        img, r, n = imgs[i]
        out = r.plot(img=img.copy(), boxes=False, labels=False, kpt_line=False, probs=False) if n else img.copy()
        cv2.putText(out, f"{n} person(s)  +{(per[i]['ts_us']-frames[0]['ts_us'])/1e6:.2f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        fn = "det_" + per[i]["file"]
        cv2.imwrite(os.path.join(event_dir, fn), out)
        keys.append(dict(file=fn, ts_us=per[i]["ts_us"], n=n))
    counts = [p["n"] for p in per]
    posts = [q for p in per for q in p["postures"]]
    post = max(set(posts), key=posts.count) if posts else "n/a"
    n_max = max(counts) if counts else 0
    with_person = sum(1 for c in counts if c)
    if n_max == 0:
        text = "No person detected in this chunk (motion by an object, camera covered/moved, light change or something small)."
    else:
        text = f"Up to {n_max} person(s), visible in {with_person}/{len(per)} sampled frames; mostly {post}; {act}."
    timeline = _timeline(per, frames[0]["ts_us"])
    if n_max:
        text += " Timeline: " + "; ".join(f"+{g['start_s']:.1f}–{g['end_s']:.1f} s {g['text']}" for g in timeline) + "."
    report["detections"] = dict(text=text, timeline=timeline, keyframes=keys, frames_analyzed=len(per), max_persons=n_max, posture=post, activity=act)
    report["sections"]["People (YOLO11n-pose)"] = text
    report["summary"] = text + " | " + report.get("summary", "")
