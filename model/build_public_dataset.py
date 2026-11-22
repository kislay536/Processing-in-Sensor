#!/usr/bin/env python3
"""Public-data half of the distillation set, in the board's input format (128x96 gray, 5x5 box downscale of a 640x480 image).

  .venv/bin/python model/build_public_dataset.py

  scene_* Imagenette photos + coco128 scenes with people (centre-cropped to 640x480), labelled by YuNet at 320x240: face (>=32 px wide at 320x240, score>=0.6),
          no face (nothing found at score>=0.3), anything in between is stored but left out of training by train_face.py.
  lfw_*   LFW faces (many identities) pasted at random size (face 64..280 px wide at 640x480) and position onto scene images in which
          YuNet finds no face, with a feathered edge. A composite counts as a face only if YuNet confirms it on the composite.
Splits are by image / identity so the test halves share no scene and no person with the training halves.
"""
import glob
import os
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from board_sim.detector import downscale_5x5

rng = np.random.default_rng(7)
yunet = cv2.FaceDetectorYN.create(os.path.join(ROOT, "model/pretrained/yunet.onnx"), "", (320, 240), score_threshold=0.3, nms_threshold=0.3, top_k=10)
MIN_W = 32


def scores(bgr640):
    small = cv2.resize(bgr640, (320, 240), interpolation=cv2.INTER_AREA)
    yunet.setInputSize((320, 240))
    _, f = yunet.detect(small)
    if f is None or not len(f):
        return 0.0, 0.0
    big = f[f[:, 2] >= MIN_W]
    return (float(big[:, 14].max()) if len(big) else 0.0), float(f[:, 14].max())


def to_128x96(bgr640):
    return downscale_5x5(cv2.cvtColor(bgr640, cv2.COLOR_BGR2GRAY))


def fit_640x480(img):
    h, w = img.shape[:2]
    s = max(640 / w, 480 / h)
    img = cv2.resize(img, (max(640, round(w * s)), max(480, round(h * s))), interpolation=cv2.INTER_AREA)
    y0, x0 = (img.shape[0] - 480) // 2, (img.shape[1] - 640) // 2
    return img[y0:y0 + 480, x0:x0 + 640].copy()


def blend(bg, patch, rng):
    """Paste patch (BGR) at a random position with a feathered elliptical mask and brightness matching (same for faces and decoys)."""
    ph, pw = patch.shape[:2]
    x0, y0 = int(rng.integers(0, 640 - pw + 1)), int(rng.integers(0, 480 - ph + 1))
    mask = np.zeros((ph, pw), np.float32)
    cv2.ellipse(mask, (pw // 2, ph // 2), (int(pw * 0.46), int(ph * 0.48)), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), max(2.0, pw * 0.05))[..., None]
    roi = bg[y0:y0 + ph, x0:x0 + pw].astype(np.float32)
    p = patch.astype(np.float32) * (roi.mean() / max(patch.mean(), 1.0)) ** rng.uniform(0.3, 0.9)
    bg[y0:y0 + ph, x0:x0 + pw] = np.clip(mask * p + (1 - mask) * roi, 0, 255).astype(np.uint8)
    return bg


def main():
    pub = os.path.join(ROOT, "data/public")
    items = []                                                # (path, split)
    imn = sorted(glob.glob(os.path.join(pub, "imagenette2-160/train/*/*.JPEG")))
    imv = sorted(glob.glob(os.path.join(pub, "imagenette2-160/val/*/*.JPEG")))
    items += [(p, "train") for p in rng.permutation(imn)[:3000]]
    items += [(p, "test") for p in rng.permutation(imv)[:600]]
    items += [(p, "train") for p in sorted(glob.glob(os.path.join(pub, "coco128/images/train2017/*.jpg")))]   # natural scenes with people
    X, S, A, G = [], [], [], []
    clean_bg = {"train": [], "test": []}
    for i, (path, split) in enumerate(items):
        img = fit_640x480(cv2.imread(path))
        big, anyf = scores(img)
        X.append(to_128x96(img)); S.append(big); A.append(anyf); G.append(f"scene_{split}")
        if anyf < 0.3 and len(clean_bg[split]) < 1500:
            clean_bg[split].append(img)
        if i % 1000 == 0:
            print("scenes", i, flush=True)
    for sp in ("train", "test"):
        m = np.array(G) == f"scene_{sp}"
        b_, a_ = np.array(S)[m], np.array(A)[m]
        print(f"scene_{sp}: {m.sum()} images: face {(b_ >= 0.6).sum()} | no face {(a_ < 0.3).sum()} | uncertain {((b_ < 0.6) & (a_ >= 0.3)).sum()}", flush=True)

    lfw_root = os.path.join(ROOT, "data/public/lfw_funneled")
    people = sorted(d for d in os.listdir(lfw_root) if os.path.isdir(os.path.join(lfw_root, d)))
    split_at = int(len(people) * 0.9)
    yun = cv2.FaceDetectorYN.create(os.path.join(ROOT, "model/pretrained/yunet.onnx"), "", (250, 250), score_threshold=0.6, nms_threshold=0.3, top_k=5)
    made = {"train": 0, "test": 0}
    kept = {"train": 0, "test": 0}
    for sp, plist, target in (("train", people[:split_at], 3500), ("test", people[split_at:], 500)):
        order = rng.permutation(len(plist))
        for pi in order:
            if made[sp] >= target:
                break
            files = sorted(glob.glob(os.path.join(ROOT, "data/public/lfw_funneled", plist[pi], "*.jpg")))
            f = cv2.imread(files[int(rng.integers(len(files)))])
            _, d = yun.detect(f)
            if d is None or not len(d):
                continue
            fw = float(d[0, 2])
            tw = float(np.exp(rng.uniform(np.log(64), np.log(280))))
            scale = min(tw / fw, 470 / 250)
            patch = cv2.resize(f, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            if rng.random() < 0.5:
                patch = patch[:, ::-1]
            bg = blend(clean_bg[sp][int(rng.integers(len(clean_bg[sp])))].copy(), patch, rng)
            made[sp] += 1
            big, anyf = scores(bg)
            if big < 0.6:
                continue                                  # YuNet does not see a face in the composite -> not a clean positive
            X.append(to_128x96(bg)); S.append(big); A.append(anyf); G.append(f"lfw_{sp}")
            kept[sp] += 1
        print(f"lfw_{sp}: made {made[sp]}, YuNet-confirmed {kept[sp]}", flush=True)
    # decoys: random patches cut from other scene images, pasted with the identical blend, labelled no-face (so the blend is not a cue)
    for sp, target in (("train", 3000), ("test", 400)):
        n = 0
        while n < target:
            bg = clean_bg[sp][int(rng.integers(len(clean_bg[sp])))].copy()
            donor = clean_bg[sp][int(rng.integers(len(clean_bg[sp])))]
            sz = int(np.exp(rng.uniform(np.log(140), np.log(470))))
            dy, dx = int(rng.integers(0, 480 - sz + 1)), int(rng.integers(0, 640 - sz + 1))
            bg = blend(bg, donor[dy:dy + sz, dx:dx + sz], rng)
            big, anyf = scores(bg)
            if anyf >= 0.3:
                continue
            X.append(to_128x96(bg)); S.append(big); A.append(anyf); G.append(f"decoy_{sp}")
            n += 1
        print(f"decoy_{sp}: {n}", flush=True)
    np.savez_compressed(os.path.join(ROOT, "data/face/public.npz"), x=np.stack(X), score=np.array(S, np.float32),
                        score_any=np.array(A, np.float32), group=np.array(G))
    print("saved data/face/public.npz", len(X))


if __name__ == "__main__":
    main()
