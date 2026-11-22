#!/usr/bin/env python3
"""Laptop relay: a dumb pipe from the camera to the board. No decoding, no analysis.

  python3 relay/relay.py --board 192.168.7.2 --source camera --device 2 --keep-every 5     (30 fps camera -> 6 fps to the board)
  python3 relay/relay.py --board 127.0.0.1 --source synthetic --seconds 20     (for testing)
"""
import argparse
import os
import socket
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import proto

W, H = 640, 480


def camera_source(device):
    import cv2
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        sys.exit(f"cannot open /dev/video{device}")
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)           # raw YUYV, untouched
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    while True:
        ok, f = cap.read()
        if not ok:
            continue
        yield f.tobytes()


def synthetic_source(motion_at, motion_dur, period):
    """Static textured scene with a bright block that moves during [motion_at, motion_at+dur) of each period."""
    rng = np.random.default_rng(1)
    base = (110 + rng.integers(-6, 6, (H, W))).astype(np.uint8)
    t0 = time.time()
    while True:
        t = (time.time() - t0) % period
        y = base.copy()
        y += rng.integers(0, 3, (H, W), dtype=np.uint8)            # sensor noise
        if motion_at <= t < motion_at + motion_dur:
            x = int(40 + (t - motion_at) * 120) % (W - 160)
            y[160:340, x:x + 140] = 235
        f = np.empty((H, W, 2), np.uint8); f[..., 0] = y; f[..., 1] = 128
        yield f.tobytes()


def synthetic_audio(sock, lock, sound_at, sound_dur, period, wav_path, stop):
    """Test microphone for the relay: quiet noise, plus a sound (440 Hz tone + noise, or a wav file) during [sound_at, +dur) of each period.
    16 kHz mono, 512-sample blocks paced in real time, sent as stream 3 (the board's audio ring / audio_bands IP)."""
    import wave
    rng = np.random.default_rng(2)
    clip = None
    if wav_path:
        with wave.open(wav_path) as w:
            raw = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64)
            if w.getnchannels() > 1:
                raw = raw.reshape(-1, w.getnchannels()).mean(axis=1)
            if w.getframerate() != 16000:
                raw = np.interp(np.arange(0, len(raw), w.getframerate() / 16000), np.arange(len(raw)), raw)
            clip = raw.astype(np.int16)
    t0, n, fid = time.time(), 0, 0
    while not stop.is_set():
        t = (time.time() - t0) % period
        x = rng.normal(0, 12, 512)
        if sound_at <= t < sound_at + sound_dur:
            if clip is not None:
                o = int((t - sound_at) * 16000) % max(len(clip) - 512, 1)
                x = x + clip[o:o + 512].astype(np.float64)
            else:
                ph = (np.arange(512) + n * 512) / 16000.0
                x = x + 3000 * np.sin(2 * np.pi * 440 * ph) + rng.normal(0, 800, 512)
        blk = np.clip(x, -32768, 32767).astype(np.int16).tobytes()
        pkt = proto.FRM_HDR.pack(proto.MAGIC_FRM, fid, int(time.time() * 1e6), 512, 1, proto.FMT_PCM16, 1024, __import__("zlib").crc32(blk)) + blk
        with lock:
            try:
                sock.sendall(pkt)
            except OSError:
                return
        fid += 1; n += 1
        time.sleep(max(0.0, t0 + n * 512 / 16000 - time.time()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=proto.PORT_FRAMES)
    ap.add_argument("--source", choices=["camera", "synthetic"], default="camera")
    ap.add_argument("--device", type=int, default=2)
    ap.add_argument("--fps", type=float, default=30.0, help="source frame rate; the camera sets it, the synthetic source is paced to it")
    ap.add_argument("--keep-every", type=int, default=5, help="send frame k only if k %% N == 0 (5 = drop 80%%)")
    ap.add_argument("--log", default="", help="write one JSON line per sent frame (fid, source index, crc32)")
    ap.add_argument("--cfg", nargs="*", default=[], help="detector parameters to set on the board at connect, e.g. max_chunk_s=3 pre=4 (CFG1; unlisted ones go to defaults)")
    ap.add_argument("--seconds", type=float, default=0, help="0 = run until Ctrl-C")
    ap.add_argument("--motion-at", type=float, default=12.0)
    ap.add_argument("--motion-dur", type=float, default=4.0)
    ap.add_argument("--period", type=float, default=30.0)
    ap.add_argument("--audio-synth", action="store_true", help="also send a synthetic microphone: quiet noise + a sound at --sound-at/--sound-dur")
    ap.add_argument("--sound-at", type=float, default=12.0)
    ap.add_argument("--sound-dur", type=float, default=4.0)
    ap.add_argument("--audio-wav", default="", help="play this wav (any rate, mono/stereo) during the sound instead of a tone")
    a = ap.parse_args()

    src = camera_source(a.device) if a.source == "camera" else synthetic_source(a.motion_at, a.motion_dur, a.period)
    while True:
        try:
            s = socket.create_connection((a.board, a.port), timeout=5)
            break
        except OSError as e:
            print("waiting for board...", e, flush=True); time.sleep(1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"relay connected to {a.board}:{a.port}; keeping 1 of every {a.keep_every} frames from {a.source}", flush=True)
    import json
    import zlib
    if a.cfg:
        s.sendall(proto.pack_cfg(**{k: int(v) for k, v in (x.split("=") for x in a.cfg)}))
    import threading
    lock, stop = threading.Lock(), threading.Event()
    if a.audio_synth:
        threading.Thread(target=synthetic_audio, args=(s, lock, a.sound_at, a.sound_dur, a.period, a.audio_wav, stop), daemon=True).start()
    logf = open(a.log, "w") if a.log else None
    fid, k, t_start = 0, 0, time.time()
    sent = 0
    for payload in src:
        now = time.time()
        if a.source == "synthetic":                      # the camera paces itself; the synthetic source needs a clock
            time.sleep(max(0.0, t_start + (k + 1) / a.fps - time.time()))
        keep = k % a.keep_every == 0
        k += 1
        if keep:
            assert len(payload) == W * H * 2, f"unexpected frame size {len(payload)}"
            with lock:
                s.sendall(proto.pack_frame(fid, int(now * 1e6), W, H, payload))
            if logf:
                logf.write(json.dumps(dict(fid=fid, src_index=k - 1, crc=zlib.crc32(payload))) + "\n"); logf.flush()
            fid += 1; sent += len(payload)
        if a.seconds and now - t_start > a.seconds:
            break
    stop.set()
    print(f"relay done: read {k} camera frames, sent {fid} ({100*fid/max(k,1):.0f}%), {sent/1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
