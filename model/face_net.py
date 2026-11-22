"""Tiny fully-convolutional face-presence network for the FPGA. Input: 1x96x128 gray (the board's 5x5-box-downscaled Y plane).
Output: a 6x8 logit map; the frame score is its global max. Only 3x3 / 1x1 convs + ReLU (+ BatchNorm, folded at export)."""
import torch
import torch.nn as nn


def block(ci, co, stride):
    return nn.Sequential(nn.Conv2d(ci, co, 3, stride, 1, bias=False), nn.BatchNorm2d(co), nn.ReLU(inplace=True))


class FaceNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(block(1, 8, 2), block(8, 16, 2), block(16, 24, 2), block(24, 32, 1), block(32, 32, 2), block(32, 32, 1))
        self.head = nn.Conv2d(32, 1, 1)

    def forward(self, x):                       # x: (B,1,96,128) float in [0,1]
        return self.head(self.body(x))          # (B,1,6,8) logits

    def score_logit(self, x):
        return self.forward(x).flatten(1).amax(1)
