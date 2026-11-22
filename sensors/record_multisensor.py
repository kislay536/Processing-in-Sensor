#!/usr/bin/env python3
"""Record colour + IR + microphone at the same time with labelled phases, to tune the three cheap detectors.

  .venv/bin/python sensors/record_multisensor.py

Phases are announced by voice. The first CUE seconds of each phase are marked 'cue' (the spoken instruction is audible on the mic) and
excluded from tuning. Stored under data/sensors/<session>/:
  rgb_y128x96.npy / rgb_ts.npy    5x5-box-downscaled Y of every 5th colour frame (what the board would see), + timestamps
  ir_y96x96.npy / ir_ts.npy       the same for the IR camera (480x480 -> 96x96)
  rgb_raw.npy / ir_raw.npy        the first RAW_N kept frames at full size (test vectors for the hardware detectors)
  audio.wav + audio_t0.json       16 kHz mono PCM and the wall-clock time of its first sample
  phases.json                     phase name, start, end (wall clock), whether motion/sound were requested
"""
import json
import os
import subprocess
import sys
import threading
import time
import wave

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CUE = 7.0
RAW_N = 60
PHASES = [  # name, seconds (after the cue), motion?, sound?, instruction
    ("quiet", 30, 0, 0, "Quiet. Stay completely still and silent, and stay out of the camera view if you can."),
    ("motion_only", 25, 1, 0, "Motion only. Move in front of the cameras: wave your arms, walk about. No talking, no noise."),
    ("sound_only", 25, 0, 1, "Sound only. Step out of view. Clap, snap your fingers, knock on the table, talk loudly."),
    ("both", 25, 1, 1, "Both. Move in front of the cameras and make noise at the same time."),
    ("quiet2", 20, 0, 0, "Quiet again. Stay still and silent."),
]


def box5(y):
    h, w = y.shape
    s = y.astype(np.uint32).reshape(h // 5, 5, w // 5, 5).sum(axis=(1, 3))
    return (s // 25).astype(np.uint8)


class Cam(threading.Thread):
    def __init__(self, dev, fourcc, W, H, ymode, keep=5):
        super().__init__(daemon=True)
        self.cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            sys.exit(f"cannot open /dev/video{dev}")
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, W); self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.W, self.H, self.ymode, self.keep = W, H, ymode, keep
        self.small, self.ts, self.raw, self.total, self.stop = [], [], [], 0, False

    def run(self):
        k = 0
        while not self.stop:
            ok, f = self.cap.read()
            t = time.time()
            if not ok or f is None:
                continue
            self.total += 1
            if k % self.keep == 0:
                y = f.reshape(self.H, self.W, 2)[:, :, 0] if self.ymode == "yuyv" else f.reshape(self.H, self.W)
                self.small.append(box5(y)); self.ts.append(t)
                if len(self.raw) < RAW_N:
                    self.raw.append(y.copy())
            k += 1


def cue(text):
    subprocess.Popen(["notify-send", "-t", "6000", "PiSe recording", text], stderr=subprocess.DEVNULL)
    subprocess.Popen(["spd-say", "-w", text], stderr=subprocess.DEVNULL)
    subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"], stderr=subprocess.DEVNULL)
    print(">>", text, flush=True)


def main():
    sess = os.path.join(ROOT, "data/sensors", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(sess)
    rgb = Cam(2, "YUYV", 640, 480, "yuyv")
    ir = Cam(4, "GREY", 480, 480, "grey")
    for c in (rgb, ir):
        for _ in range(10):
            c.cap.read()
    audio, a_t0 = bytearray(), [None]
    arec = subprocess.Popen(["arecord", "-D", "plughw:2,0", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-q"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def pump():
        while True:
            b = arec.stdout.read(3200)
            if not b:
                break
            if a_t0[0] is None:
                a_t0[0] = time.time()
            audio.extend(b)
    threading.Thread(target=pump, daemon=True).start()
    rgb.start(); ir.start()
    cue("Recording starts in 15 seconds. Stand in front of the cameras.")
    time.sleep(15)
    phases = []
    for name, secs, mot, snd, say in PHASES:
        t_start = time.time()
        cue(say)
        time.sleep(CUE + secs)
        phases.append(dict(name=name, start=t_start, cue_end=t_start + CUE, end=time.time(), motion=mot, sound=snd))
        print(f"   {name}: rgb {len(rgb.small)} ir {len(ir.small)} frames so far, audio {len(audio)/32000:.0f} s", flush=True)
    rgb.stop = ir.stop = True
    arec.terminate()
    time.sleep(0.5)
    np.save(f"{sess}/rgb_y128x96.npy", np.stack(rgb.small)); np.save(f"{sess}/rgb_ts.npy", np.array(rgb.ts))
    np.save(f"{sess}/ir_y96x96.npy", np.stack(ir.small)); np.save(f"{sess}/ir_ts.npy", np.array(ir.ts))
    np.save(f"{sess}/rgb_raw.npy", np.stack(rgb.raw)); np.save(f"{sess}/ir_raw.npy", np.stack(ir.raw))
    w = wave.open(f"{sess}/audio.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(bytes(audio)); w.close()
    json.dump(dict(t0=a_t0[0]), open(f"{sess}/audio_t0.json", "w"))
    json.dump(phases, open(f"{sess}/phases.json", "w"), indent=1)
    print(f"camera frames read: rgb {rgb.total}, ir {ir.total}; kept 1/5: rgb {len(rgb.small)}, ir {len(ir.small)}", flush=True)
    cue("Recording finished. Thank you.")
    print("saved to", sess, flush=True)


if __name__ == "__main__":
    main()
