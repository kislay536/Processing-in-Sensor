#!/usr/bin/env python3
"""Distil YuNet into FaceNet. Train on some groups, test on a held-out group.

  .venv/bin/python model/train_face.py --test s1_tilted
"""
import argparse
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from face_net import FaceNet

POS_T, NEG_T = 0.6, 0.3          # YuNet score >= POS_T -> face; < NEG_T -> no face; in between = uncertain, left out


def augment(x):
    B = x.shape[0]
    s = torch.empty(B, device=x.device).uniform_(0.8, 1.25)
    tx, ty = torch.empty(B, device=x.device).uniform_(-0.12, 0.12), torch.empty(B, device=x.device).uniform_(-0.12, 0.12)
    flip = (torch.rand(B, device=x.device) < 0.5).float() * 2 - 1
    theta = torch.zeros(B, 2, 3, device=x.device)
    theta[:, 0, 0], theta[:, 1, 1], theta[:, 0, 2], theta[:, 1, 2] = flip / s, 1 / s, tx, ty
    x = F.grid_sample(x, F.affine_grid(theta, x.shape, align_corners=False), padding_mode="border", align_corners=False)
    gain = torch.empty(B, 1, 1, 1, device=x.device).uniform_(0.6, 1.4)
    bias = torch.empty(B, 1, 1, 1, device=x.device).uniform_(-0.15, 0.15)
    x = (x ** torch.empty(B, 1, 1, 1, device=x.device).uniform_(0.7, 1.4)) * gain + bias
    return (x + 0.02 * torch.randn_like(x)).clamp(0, 1)


def auc(score, y):
    o = np.argsort(score); r = np.empty(len(o)); r[o] = np.arange(1, len(o) + 1)
    p = y.sum(); n = len(y) - p
    return float((r[y == 1].sum() - p * (p + 1) / 2) / (p * n)) if p and n else float("nan")


def evaluate(model, x, y, dev, name):
    model.eval()
    with torch.no_grad():
        logit = torch.cat([model.score_logit(x[i:i + 256].to(dev)) for i in range(0, len(x), 256)]).cpu().numpy()
    p = 1 / (1 + np.exp(-logit))
    print(f"\n{name}: {len(y)} frames ({int(y.sum())} face / {int((1-y).sum())} no-face), AUC {auc(p, y):.3f}")
    print(f"  {'thr':>5}{'precision':>11}{'recall':>8}{'false-pos':>11}{'missed':>8}")
    for t in (0.3, 0.5, 0.7, 0.9):
        pred = p >= t
        tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
        print(f"  {t:>5}{tp/max(tp+fp,1):>11.3f}{tp/max(tp+fn,1):>8.3f}{fp:>11}{fn:>8}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="scene_train,lfw_train,decoy_train,vtest_video", help="comma-separated groups to train on; every other group is a held-out test")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--out", default=os.path.join(ROOT, "model/face_net.pt"))
    a = ap.parse_args()
    torch.manual_seed(0); np.random.seed(0)
    parts = [np.load(os.path.join(ROOT, f"data/face/{n}.npz")) for n in ("dataset", "public")]
    X = np.concatenate([p["x"] for p in parts]); S = np.concatenate([p["score"] for p in parts])
    A = np.concatenate([p["score_any"] for p in parts]); G = np.concatenate([p["group"] for p in parts])
    keep = (S >= POS_T) | (A < NEG_T)         # face (big, confident) or no face at all; everything in between is left out
    Y = (S >= POS_T).astype(np.float32)
    train_groups = set(a.train.split(","))
    tr = np.isin(G, list(train_groups)) & keep
    te_groups = [g for g in sorted(set(G)) if g not in train_groups]
    dev = "cuda"
    xt = torch.from_numpy(X[tr]).float().div(255).unsqueeze(1).to(dev); yt = torch.from_numpy(Y[tr]).to(dev)
    print(f"train {int(tr.sum())} frames ({int(Y[tr].sum())} face), groups: {sorted(set(G[tr]))}")
    model = FaceNet().to(dev)
    print("parameters:", sum(p.numel() for p in model.parameters()))
    opt = torch.optim.AdamW(model.parameters(), 3e-3, weight_decay=1e-4)
    steps = a.epochs * ((len(xt) + 63) // 64)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps)
    pw = ((len(yt) - yt.sum()) / yt.sum()).clone().detach()
    t0 = time.time()
    for ep in range(a.epochs):
        model.train(); perm = torch.randperm(len(xt), device=dev); tot = 0
        for i in range(0, len(xt), 64):
            idx = perm[i:i + 64]
            loss = F.binary_cross_entropy_with_logits(model.score_logit(augment(xt[idx])), yt[idx], pos_weight=pw)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(idx)
        if ep % 10 == 9 or ep == a.epochs - 1:
            print(f"epoch {ep+1:>3} loss {tot/len(xt):.4f}  ({time.time()-t0:.0f}s)", flush=True)
    torch.save(model.state_dict(), a.out)
    evaluate(model, torch.from_numpy(X[tr]).float().div(255).unsqueeze(1), Y[tr], dev, "TRAIN (sanity)")
    for g in te_groups:
        m = (G == g) & keep
        if m.sum() and 0 < Y[m].sum() < m.sum():
            evaluate(model, torch.from_numpy(X[m]).float().div(255).unsqueeze(1), Y[m], dev, f"HELD-OUT {g}")
        elif m.sum():
            print(f"\nHELD-OUT {g}: {int(m.sum())} frames, all {'face' if Y[m].all() else 'no-face'} (AUC undefined)")

if __name__ == "__main__":
    main()
