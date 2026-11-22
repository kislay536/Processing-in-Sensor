#!/usr/bin/env python3
"""PiSe dashboard: one process that owns the camera, relays 1 of every N frames to the board, and serves a web page.

  .venv/bin/python ui/server.py --board 192.168.7.2          then open http://127.0.0.1:8765
  .venv/bin/python ui/server.py --no-board                   camera panel only

Panels (what is real and what is not):
  1. LIVE CAMERA      frames straight from /dev/video2 (raw YUYV 640x480, ~30 fps), JPEG-encoded only for the browser.
  2. FPGA BOARD       the newest frame read BACK from the Zedboard's DDR ring over Ethernet (REQ1/RSP1), ~2 Hz. A frame is
                      marked "verified" only if the board's CRC recomputed from DDR equals the CRC the relay computed.
  3. DETECTOR/EVENTS  live state of the image-change detector that runs in the FPGA fabric (DET1 over the same connection:
                      score, reason, 8x8 cell map, parameters you can change) and the event windows the board sends to the GPU stage
                      on :5001 (this process receives them, saves events/event_NNNN and runs the analyzer cascade).
The relay path to the board is the same raw bytes as relay/relay.py; the board allows one connection, so run either, not both.
"""
import argparse
import collections
import json
import wave
import os
import queue
import shutil
import socket
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from common import proto
from gpu.analyzers import run_cascade, yolo as yolo_an
import subprocess as _sp
from gpu.chunks import ChunkAssembler
try:   # optional: energy / bandwidth analysis (self-contained folder energy/)
    import energy as _energy
except Exception:
    _energy = None

W, H = 640, 480
UI_DIR = os.path.dirname(os.path.abspath(__file__))


def to_jpeg(yuyv, q=75):
    bgr = cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUY2)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
    return buf.tobytes() if ok else None


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.live_jpeg, self.live_id = None, 0
        self.board_jpeg, self.board_id = None, 0
        self.cam_frames, self.cam_fps, self.cam_err = 0, 0.0, ""
        self.kept, self.send_drops, self.sent_ok = 0, 0, 0
        self.sent_crc = {}                       # fid -> crc32 the relay computed (last 400)
        self.connected = False
        self.board_stats = None
        self.board_slot = None                   # dict about the frame currently shown in the board panel
        self.mbps = 0.0
        self.ir_frames, self.ir_fps, self.ir_err = 0, 0.0, ""
        self.mic_blocks, self.mic_err = 0, ""
        self.mic_ring = collections.deque(maxlen=1500)      # (ts_us, 1024 B PCM16) last ~48 s of microphone blocks, for audio-only chunks
        self.cam_on, self.mic_on = True, True       # source switches (POST /api/sources): off = device released, nothing sent to the board
        self.drop_n = 0                          # frames dropped after each frame sent to the board (0 = send every frame)
        self.det = None                          # latest DET1 from the board
        self.det_at = 0.0
        self.history = []                        # [col_frames, score, changed, fired] per new colour frame
        self.events_rx, self.event_err, self.gpu_connected = 0, "", False
        self.stream_frames = 0
        self.stream_audio_blocks = 0
        self.aud = []                            # [t, rms, baseline, fired, aud_blocks] one per new audio block seen by the poller (about 15 per second)
        self.tl = []                             # [t, video_fired, audio_fired, event_state, trig_mode] per detector poll (about 4 per second)


S = State()


class BoardLink:
    """One TCP connection carries frames out and REQ1/RSP1/STS1 back (the firmware parses both on one connection)."""

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.sock, self.send_lock = None, threading.Lock()
        self.q = queue.Queue(maxsize=2)
        self.reply = queue.Queue()
        threading.Thread(target=self._sender, daemon=True).start()
        threading.Thread(target=self._connect_loop, daemon=True).start()
        threading.Thread(target=self._poller, daemon=True).start()

    def push(self, item):
        try:
            self.q.put_nowait(item)
        except queue.Full:
            try:
                self.q.get_nowait()
                S.send_drops += 1
            except queue.Empty:
                pass
            self.q.put_nowait(item)

    def _connect_loop(self):
        while True:
            if self.sock is None:
                try:
                    s = socket.create_connection((self.host, self.port), timeout=3)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.settimeout(None)
                    self.sock = s
                    S.connected = True
                    threading.Thread(target=self._reader, args=(s,), daemon=True).start()
                except OSError:
                    S.connected = False
            time.sleep(1)

    def _drop(self, s):
        if self.sock is s:
            self.sock = None
            S.connected = False
        try:
            s.close()
        except OSError:
            pass

    def _sender(self):
        t_win, b_win = time.time(), 0
        while True:
            fid, ts, payload, crc = self.q.get()
            s = self.sock
            if s is None:
                continue
            msg = proto.FRM_HDR.pack(proto.MAGIC_FRM, fid, ts, W, H, proto.FMT_YUYV, len(payload), crc) + payload
            try:
                with self.send_lock:
                    s.sendall(msg)
                S.sent_ok += 1
                b_win += len(msg)
                now = time.time()
                if now - t_win >= 2:
                    S.mbps = b_win * 8 / 1e6 / (now - t_win)
                    t_win, b_win = now, 0
            except OSError:
                self._drop(s)

    def _reader(self, s):
        try:
            while True:
                magic = proto.recv_exact(s, 4)
                if magic == proto.MAGIC_STS:
                    rest = proto.recv_exact(s, proto.STS_MSG.size - 4)
                    _, fr, ce, bl, gp, lf, nb = proto.STS_MSG.unpack(magic + rest)
                    self.reply.put(("STS", dict(frames_rx=fr, crc_err=ce, bad_len=bl, fid_gaps=gp, last_fid=lf, bytes_rx=nb)))
                elif magic == proto.MAGIC_DET:
                    rest = proto.recv_exact(s, proto.DET_MSG.size - 4)
                    self.reply.put(("DET", proto.parse_det(magic + rest)))
                elif magic == proto.MAGIC_RSP:
                    rest = proto.recv_exact(s, proto.RSP_HDR.size - 4)
                    _, sl, fid, ln, crc_ddr, crc_rx = proto.RSP_HDR.unpack(magic + rest)
                    self.reply.put(("RSP", dict(slot=sl, fid=fid, crc_ddr=crc_ddr, crc_rx=crc_rx), proto.recv_exact(s, ln)))
                else:
                    raise ValueError(f"unexpected board message {magic!r}")
        except (OSError, ConnectionError, ValueError):
            self._drop(s)

    def _request(self, slot, timeout=3.0):
        s = self.sock
        if s is None:
            return None
        while not self.reply.empty():
            self.reply.get_nowait()
        try:
            with self.send_lock:
                s.sendall(proto.REQ_MSG.pack(proto.MAGIC_REQ, slot, 0))
            return self.reply.get(timeout=timeout)
        except (OSError, queue.Empty):
            return None

    def send_raw(self, msg):
        """Atomically send one complete message (IR frame / audio block) on the board connection."""
        s = self.sock
        if s is None:
            return False
        try:
            with self.send_lock:
                s.sendall(msg)
            return True
        except OSError:
            self._drop(s)
            return False

    def send_cfg(self, **kw):
        """Change detector parameters on the board (CFG1). Unspecified parameters keep the board's current values."""
        base = dict(S.det["params"]) if S.det else dict(proto.PARAM_DEFAULTS)
        base.update({k: int(v) for k, v in kw.items() if k in proto.PARAM_NAMES})
        base.setdefault("reset", 0)
        if "reset" not in kw:
            base["reset"] = 0
        s = self.sock
        if s is None:
            return False
        try:
            with self.send_lock:
                s.sendall(proto.pack_cfg(**base))
            return True
        except OSError:
            return False

    def _poller(self):
        last_slot_t, last_sts, sts = 0.0, 0.0, None
        while True:
            time.sleep(0.06)                                   # detector registers (incl. audio level) about 15 times a second
            if time.time() - last_sts >= 0.25 or sts is None:
                r = self._request(proto.REQ_STATS)
                if not r or r[0] != "STS":
                    sts = None
                    continue
                sts = r[1]; S.board_stats = sts; last_sts = time.time()
            d = self._request(proto.REQ_DET)
            if d and d[0] == "DET":
                S.det, S.det_at = d[1], time.time()
                if not S.aud or S.aud[-1][4] != d[1]["aud_blocks"]:
                    S.aud.append([S.det_at, d[1]["aud_rms"], d[1]["aud_base_rms"], int(bool(d[1]["aud_fired"])), d[1]["aud_blocks"]]); del S.aud[:-200]
                S.tl.append([S.det_at, int(bool(d[1]["fired"])), int(bool(d[1]["aud_fired"])), d[1]["event_state"], d[1]["params"]["trig_mode"]])
                del S.tl[:-4000]
                if not S.history or S.history[-1][0] != d[1]["col_frames"]:
                    S.history.append([d[1]["col_frames"], d[1]["score"], d[1]["changed"], d[1]["fired"]])
                    del S.history[:-150]
            n = sts["frames_rx"]
            if n == 0 or time.time() - last_slot_t < 0.45:
                continue
            slot = (n - 1) % proto.NSLOT
            r = self._request(slot)
            if not r or r[0] != "RSP":
                continue
            last_slot_t = time.time()
            m, payload = r[1], r[2]
            if len(payload) != W * H * 2:
                continue
            jpg = to_jpeg(np.frombuffer(payload, np.uint8).reshape(H, W, 2))
            relay_crc = S.sent_crc.get(m["fid"])
            with S.lock:
                S.board_jpeg, S.board_id = jpg, S.board_id + 1
                S.board_slot = dict(slot=slot, fid=m["fid"], crc_ddr=m["crc_ddr"], crc_rx=m["crc_rx"], relay_crc=relay_crc,
                                    verified=(relay_crc is not None and m["crc_ddr"] == m["crc_rx"] == relay_crc),
                                    shown_at=time.time())


def _open_cam(device):
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        S.cam_err = f"cannot open /dev/video{device} (another program using it?)"
        return None
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    S.cam_err = ""
    return cap


def camera_loop(device, keep_every, link, synthetic):
    cap = None
    if not synthetic:
        cap = _open_cam(device)
        if cap is None:
            return
    rng = np.random.default_rng(1)
    k, fid, t0, n_win, since_sent = 0, 0, time.time(), 0, S.drop_n
    t_next = time.time()
    while True:
        if not S.cam_on:                                   # switched off: release the camera, send nothing
            if cap is not None:
                cap.release(); cap = None
            S.cam_fps = 0.0
            time.sleep(0.2); t_next = time.time()
            continue
        if not synthetic and cap is None:
            cap = _open_cam(device)
            if cap is None:
                time.sleep(1.0); continue
        if synthetic:
            t_next += 1 / 30
            time.sleep(max(0, t_next - time.time()))
            y = (110 + rng.integers(0, 6, (H, W))).astype(np.uint8)
            x = int(time.time() * 120) % (W - 120)
            y[200:320, x:x + 100] = 235
            f = np.empty((H, W, 2), np.uint8); f[..., 0] = y; f[..., 1] = 128
        else:
            ok, f = cap.read()
            if not ok or f is None or f.nbytes != W * H * 2:
                continue
            f = f.reshape(H, W, 2)
        now = time.time()
        jpg = to_jpeg(f, 70)
        with S.lock:
            S.live_jpeg, S.live_id = jpg, S.live_id + 1
        S.cam_frames += 1
        n_win += 1
        if now - t0 >= 1.0:
            S.cam_fps = n_win / (now - t0)
            t0, n_win = now, 0
        if since_sent >= S.drop_n:
            since_sent = 0
            payload = f.tobytes()
            crc = zlib.crc32(payload)
            S.sent_crc[fid] = crc
            if len(S.sent_crc) > 400:
                S.sent_crc.pop(next(iter(S.sent_crc)))
            S.kept += 1
            if link:
                link.push((fid, int(now * 1e6), payload, crc))
            fid += 1
        else:
            since_sent += 1
        k += 1


def ir_loop(device, keep_every, link):
    """IR (Hello) camera, GREY 480x480, 1 of every N frames -> board stream 2 (change_ir IP)."""
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        S.ir_err = f"cannot open /dev/video{device}"
        return
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"GREY"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    k, fid, t0, n, since_sent = 0, 0, time.time(), 0, S.drop_n
    while True:
        ok, f = cap.read()
        if not ok or f is None or f.nbytes != 480 * 480:
            continue
        n += 1
        if time.time() - t0 >= 1:
            S.ir_fps, t0, n = n, time.time(), 0
        S.ir_frames += 1
        if since_sent >= S.drop_n:
            since_sent = 0
            payload = np.ascontiguousarray(f).tobytes()
            link.send_raw(proto.FRM_HDR.pack(proto.MAGIC_FRM, fid, int(time.time() * 1e6), 480, 480, proto.FMT_GREY, len(payload),
                                             zlib.crc32(payload)) + payload)
            fid += 1
        else:
            since_sent += 1
        k += 1


def mic_loop(card, link):
    """Microphone via arecord (16 kHz, mono, S16_LE), 512-sample blocks -> board stream 3 (audio_bands IP). Switched off = arecord stopped."""
    import subprocess
    fid, p = 0, None
    while True:
        if not S.mic_on:
            if p is not None:
                p.terminate(); p.wait(); p = None
            time.sleep(0.2)
            continue
        if p is None:
            try:
                p = subprocess.Popen(["arecord", "-q", "-D", card, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                S.mic_err = ""
            except OSError as e:
                S.mic_err = str(e)
                return
        blk = p.stdout.read(1024)
        if not S.mic_on:
            continue
        if not blk or len(blk) != 1024:
            S.mic_err = "arecord stopped" if not blk else "short read"
            if not blk:
                return
            continue
        S.mic_blocks += 1
        S.mic_ring.append((int(time.time() * 1e6), blk))
        link.send_raw(proto.FRM_HDR.pack(proto.MAGIC_FRM, fid, int(time.time() * 1e6), 512, 1, proto.FMT_PCM16, 1024, zlib.crc32(blk)) + blk)
        fid += 1


ANALYSIS = dict(pending=0)


KEEP_EVENTS = int(os.environ.get("EVENTCAM_KEEP_EVENTS", "30"))      # newest chunk folders kept on disk; older ones are deleted automatically


def prune_loop(events_dir, every=20.0):
    """Delete old chunk folders (frames + audio): keep the newest KEEP_EVENTS, and never a chunk still waiting for analysis unless it is >10 min old."""
    while True:
        time.sleep(every)
        try:
            names = sorted(n for n in os.listdir(events_dir) if n.startswith("event_"))
            for n in names[:-KEEP_EVENTS] if KEEP_EVENTS > 0 else []:
                d = os.path.join(events_dir, n)
                if os.path.islink(d) or not os.path.isdir(d):
                    continue
                if not os.path.exists(os.path.join(d, "report.json")) and time.time() - os.path.getmtime(d) < 600:
                    continue
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def event_loop(host, events_dir):
    """GPU stage inside the dashboard process: receive the board's motion-gated stream (:5001), write chunks, run the analyzers."""
    os.makedirs(events_dir, exist_ok=True)
    asm = ChunkAssembler(events_dir)
    threading.Thread(target=prune_loop, args=(events_dir,), daemon=True).start()

    work = queue.Queue()

    def done(res):
        """Hand a finished chunk to the single analysis worker so a slow analysis never blocks the board's TCP stream."""
        if res:
            ANALYSIS["pending"] += 1
            work.put((time.time(), res))

    def analyse(res):
        t0 = time.time()
        d, meta = res
        report = run_cascade(d, meta)
        report["analysis_seconds"] = round(time.time() - t0, 3)
        if _energy:
            _energy.METER.note_analysis(max(1, len((report.get("scene") or {}).get("windows", []))), report["analysis_seconds"])
        with open(os.path.join(d, "report.json"), "w") as fh:
            json.dump(report, fh, indent=1)
        with open(os.path.join(d, "report.md"), "w") as fh:
            fh.write(report["markdown"])
        S.events_rx += 1
        print(f"chunk {meta['event_id']}: {meta['n_frames']} frames, {meta['duration_s']} s ({meta['end_reason']}) -> {d}", flush=True)

    def audio_only_loop():
        """Camera switched off: the board gets no frames, so it sends no chunk. The audio detector still fires (board DET), so cut the audio
        chunk here from the microphone ring (1 s before the onset until 1 s after it ends, at most 20 s) and analyse it audio-only."""
        rec = None
        while True:
            time.sleep(0.1)
            now = time.time()
            on = (not S.cam_on) and S.mic_on and S.det is not None and S.det["params"].get("trig_mode") and S.aud and S.aud[-1][3] and now - S.aud[-1][0] < 1.0
            if rec is None:
                if on:
                    rec = dict(t0=now - 1.0, last=now)
                continue
            if on:
                rec["last"] = now
            if now - rec["last"] > 1.0 or now - rec["t0"] >= 20.0 or S.cam_on or not S.mic_on:
                blocks = [b for t, b in list(S.mic_ring) if rec["t0"] * 1e6 <= t <= (rec["last"] + 0.5) * 1e6]
                ts = [t for t, b in list(S.mic_ring) if rec["t0"] * 1e6 <= t <= (rec["last"] + 0.5) * 1e6]
                rec = None
                if len(blocks) < 16:
                    continue
                lid = asm.next_id; asm.next_id += 1
                d = asm._dir(lid); os.makedirs(d, exist_ok=True)
                pcm = b"".join(blocks)
                with wave.open(os.path.join(d, "audio.wav"), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(proto.AUDIO_RATE); w.writeframes(pcm)
                x = np.frombuffer(pcm, np.int16).astype(np.float64)
                audio = dict(file="audio.wav", sample_rate=proto.AUDIO_RATE, n_blocks=len(blocks), n_samples=len(x), start_ts_us=ts[0], end_ts_us=ts[-1],
                             duration_s=round(len(x) / proto.AUDIO_RATE, 3), rms=round(float((x * x).mean() ** 0.5), 1), expected_blocks=len(blocks), complete=True, bundles=[])
                meta = dict(kind="audio", trigger_cause="audio", audio=audio, event_id=lid, board_seg=0, episode=0, chunk=0, end_reason="audio ended",
                            trigger_frame_id=0, trigger_ts_us=ts[0], motion_x1000=0, person_x1000=0, n_frames=0, start_ts_us=ts[0], end_ts_us=ts[-1],
                            duration_s=audio["duration_s"], fps=0, frames=[], bytes_received=len(pcm), received_at=time.time())
                json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=1)
                print(f"audio-only chunk {lid}: {audio['duration_s']} s -> {d}", flush=True)
                done((d, meta))

    threading.Thread(target=audio_only_loop, daemon=True).start()
    MAX_AGE_S = 6.0      # a chunk that waited longer than this is skipped: the analysis is slower than real time, show the freshest scene

    def skip(res, why):
        d, meta = res
        try:
            with open(os.path.join(d, "report.json"), "w") as fh:
                json.dump(dict(event_id=meta["event_id"], skipped=True, summary="", sections={}, note=why), fh)
        except OSError:
            pass

    def worker():
        backlog = []
        while True:
            if not backlog:
                backlog.append(work.get())
            while True:                                   # take everything that has arrived meanwhile
                try:
                    backlog.append(work.get_nowait())
                except queue.Empty:
                    break
            while _energy and _energy.METER.paused:       # the isolated GPU calibration owns the GPU: chunks wait
                time.sleep(0.5)
            now = time.time()
            fresh = [(t, r) for t, r in backlog if now - t <= MAX_AGE_S]
            for t, r in backlog:
                if now - t > MAX_AGE_S:
                    skip(r, "skipped: analysis backlog (older than %d s)" % MAX_AGE_S); ANALYSIS["pending"] -= 1
            if not fresh:
                backlog = []
                continue
            fresh.sort(key=lambda x: x[0])
            t, res = fresh.pop()                          # newest first
            backlog = fresh
            try:
                analyse(res)
            except Exception as e:
                print("analysis failed:", repr(e), flush=True)
            finally:
                ANALYSIS["pending"] -= 1

    threading.Thread(target=worker, daemon=True).start()

    while True:
        try:
            sk = socket.create_connection((host, proto.PORT_EVENTS), timeout=3)
            sk.settimeout(None)
            # a board reload never closes the old connection: keepalive makes a dead peer show up as an error within ~10 s
            sk.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sk.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 4)
            sk.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
            sk.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            S.gpu_connected = True
            while True:
                kind, m = proto.read_message(sk)
                if _energy:
                    _energy.METER.add_rx({"EVF": 48, "EVA": 48, "EVE": 44}.get(kind, 0) + len(m.get("payload", b"")))
                if kind == "EVF":
                    asm.on_frame(m)
                    S.stream_frames += 1
                elif kind == "EVA":
                    asm.on_audio(m)
                    S.stream_audio_blocks += m["n_blocks"]
                elif kind == "EVE":
                    done(asm.on_end(m))
        except (OSError, ConnectionError, ValueError) as e:
            S.gpu_connected = False
            S.event_err = str(e)
            for r in asm.flush_incomplete():
                done(r)
            time.sleep(1)


def list_events(events_dir, limit=8):
    out = []
    try:
        names = sorted((n for n in os.listdir(events_dir) if n.startswith("event_")), reverse=True)[:limit]
    except OSError:
        return out
    for n in names:
        try:
            meta = json.load(open(os.path.join(events_dir, n, "meta.json")))
        except (OSError, ValueError):
            continue
        rep = {}
        try:
            rep = json.load(open(os.path.join(events_dir, n, "report.json")))
        except (OSError, ValueError):
            pass
        frames = meta.get("frames", [])
        files = [f["file"] for f in frames]
        ts_of = {f["file"]: f.get("ts_us") for f in frames}
        trig_ts = next((f.get("ts_us") for f in frames if f.get("frame_id") == meta.get("trigger_frame_id")), None)
        step = max(1, len(files) // 6)
        out.append(dict(name=n, event_id=meta.get("event_id"), n_frames=meta.get("n_frames"), trigger_frame_id=meta.get("trigger_frame_id"),
                        received_at=meta.get("received_at"), summary=rep.get("summary", ""), finished_at=(os.path.getmtime(os.path.join(events_dir, n, "report.json")) if rep else None), det=rep.get("detections"), scene=rep.get("scene"), kind=meta.get("kind", "motion"), pending=not rep, trigger_cause=meta.get("trigger_cause"),
                        audio=(lambda a: a and dict(file=a["file"], duration_s=a["duration_s"], rms=a["rms"], complete=a["complete"]))(meta.get("audio")), trigger_ts_us=trig_ts,
                        episode=meta.get("episode"), chunk=meta.get("chunk"), end_reason=meta.get("end_reason"), duration_s=meta.get("duration_s"), fps=meta.get("fps"),
                        first_ts_us=frames[0].get("ts_us") if frames else None, last_ts_us=frames[-1].get("ts_us") if frames else None,
                        thumbs=files[::step][:6], thumb_ts_us=[ts_of[f] for f in files[::step][:6]]))
    return out


def detector_status():
    d = S.det
    if not d:
        return dict(running=False, note="No detector data from the board yet (board not connected, or no firmware with DET1).")
    out = {k: v for k, v in d.items()}
    out.update(ir_capture=dict(frames=S.ir_frames, fps=S.ir_fps, error=S.ir_err), mic=dict(blocks=S.mic_blocks, error=S.mic_err))
    out.update(running=True, age_s=round(time.time() - S.det_at, 1), history=S.history[-120:],
               gpu_connected=S.gpu_connected, events_rx=S.events_rx, stream_frames=S.stream_frames)
    return out


def status():
    b = S.board_stats
    slot = S.board_slot
    ring_fill = min(proto.NSLOT, b["frames_rx"]) if b else 0
    return dict(
        time=time.time(),
        camera=dict(fps=round(S.cam_fps, 1), frames=S.cam_frames, error=S.cam_err, width=W, height=H),
        audio=[a[:4] for a in S.aud[-60:]], sources=dict(camera=S.cam_on, audio=S.mic_on), relay=dict(drop_n=S.drop_n, kept=S.kept, sent_ok=S.sent_ok, dropped_in_sender=S.send_drops, mbps=round(S.mbps, 1)),
        board=dict(connected=S.connected, stats=b, ring_fill=ring_fill, ring_slots=proto.NSLOT,
                   shown=slot and dict({k: v for k, v in slot.items() if k != "shown_at"},
                                       age_s=round(time.time() - slot["shown_at"], 1))),
        detector=detector_status(),
        gpu=gpu_status(),
    )


def apply_profile_to_board(pid):
    """The profile decides the board's trigger mode (video only / video OR audio); other parameters keep their current values."""
    try:
        from vlm_agent import profiles
        LINK = Handler.link
        if LINK and pid in profiles.PROFILES:
            LINK.send_cfg(**profiles.PROFILES[pid]["board"])
    except Exception as e:
        print("profile -> board params failed:", repr(e), flush=True)


def run_calibration(which):
    """Isolated GPU measurement for the active profile, or for every installed profile (switching and restoring the original one)."""
    st = _energy.METER.cal_state
    try:
        import vlm_agent
        orig = vlm_agent.status().get("profile")
        ids = [orig] if which == "active" else [p["id"] for p in vlm_agent.profiles_status()["profiles"] if p["installed"]]
        for pid in ids:
            if vlm_agent.status().get("profile") != pid:
                st.update(running=True, text=f"switching to {pid}…")
                vlm_agent.switch(pid); time.sleep(1.5)
                vlm_agent.server.wait_ready(400)
                apply_profile_to_board(pid)
            _energy.calibrate(pid, Handler.events_dir)
        if orig and vlm_agent.status().get("profile") != orig:
            st.update(running=True, text="restoring the original profile…")
            vlm_agent.switch(orig); time.sleep(1.5); vlm_agent.server.wait_ready(400); apply_profile_to_board(orig)
        st.update(running=False)
    except Exception as e:
        st.update(running=False, text="calibration failed: " + repr(e))


def profile_sync_loop():
    """After a dashboard start or a board reload the board has default parameters: re-apply the active profile's trigger mode once."""
    last_frames = None
    while True:
        time.sleep(2)
        try:
            import vlm_agent
            d = S.det
            if not d:
                continue
            cur = d["col_frames"]
            first = last_frames is None
            restarted = last_frames is not None and cur < last_frames
            last_frames = cur
            if first or restarted:
                pid = vlm_agent.status().get("profile")
                if pid:
                    apply_profile_to_board(pid)
        except Exception:
            pass


GPU = dict(now={}, hist=[], procs=[], error="")
_GQ = "utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.max.sm,fan.speed"


def gpu_loop():
    """nvtop-style stats: nvidia-smi once a second, keep 120 s of history."""
    while True:
        try:
            v = [x.strip() for x in _sp.check_output(["nvidia-smi", f"--query-gpu={_GQ}", "--format=csv,noheader,nounits"], text=True, timeout=3).splitlines()[0].split(",")]
            f = lambda x: float(x) if x.replace(".", "", 1).isdigit() else None
            now = dict(zip(["util", "mem_util", "mem_used", "mem_total", "temp", "power", "power_limit", "clock", "clock_max", "fan"], map(f, v)))
            GPU["now"] = now
            GPU["hist"].append([round(time.time(), 1), now["util"], now["mem_used"]])
            del GPU["hist"][:-120]
            out = _sp.check_output(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"], text=True, timeout=3)
            GPU["procs"] = [dict(pid=int(a), name=os.path.basename(b), mem=float(c)) for a, b, c in (l.split(", ") for l in out.strip().splitlines() if l.strip())]
            GPU["error"] = ""
        except Exception as e:
            GPU["error"] = repr(e)
        time.sleep(1)


def timeline_runs(window_s=120.0):
    """Last window_s seconds of detector activity as runs [t0, t1, video, audio, sent_state, trig_mode] (consecutive equal samples merged)."""
    now = time.time()
    pts = [r for r in S.tl if r[0] >= now - window_s]
    runs = []
    for i, r in enumerate(pts):
        end = pts[i + 1][0] if i + 1 < len(pts) else min(now, r[0] + 0.5)
        end = min(end, r[0] + 1.5)                         # a gap in the polling is not activity
        key = r[1:]
        if runs and runs[-1][2:] == key and r[0] - runs[-1][1] < 1.6:
            runs[-1][1] = end
        else:
            runs.append([r[0], end] + key)
    return runs


def gpu_status():
    st = dict(yolo_an.STATE)
    st["state"] = "analysing a chunk" if st["busy"] else ("idle (model resident, waiting for motion)" if st["loaded"] else "loading model")
    vlm = None
    try:
        import vlm_agent
        vlm = dict(vlm_agent.status(), pending=ANALYSIS["pending"], profiles=vlm_agent.profiles_status())
    except Exception:
        pass
    return dict(GPU, model=dict(st, name="YOLO11n-pose"), vlm=vlm, pending=ANALYSIS["pending"], now_ts=time.time(), timeline=timeline_runs())


class Handler(BaseHTTPRequestHandler):
    events_dir = os.path.join(ROOT, "events")
    link = None
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _mjpeg(self, which):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last = -1
        try:
            while True:
                with S.lock:
                    jpg, i = (S.live_jpeg, S.live_id) if which == "live" else (S.board_jpeg, S.board_id)
                if jpg is not None and i != last:
                    last = i
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg) + jpg + b"\r\n")
                time.sleep(0.03 if which == "live" else 0.1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        except ValueError:
            return self._send(400, "text/plain", b"bad json")
        if path == "/api/config" and Handler.link:
            ok = Handler.link.send_cfg(**body)
            return self._send(200, "application/json", json.dumps(dict(ok=ok)).encode())
        if path == "/api/sources":
            if "camera" in body:
                S.cam_on = bool(body["camera"])
            if "audio" in body:
                S.mic_on = bool(body["audio"])
            if Handler.link and not (S.cam_on and S.mic_on):
                Handler.link.send_cfg(reset=1)             # clear stale detector state so nothing stays "firing" without input
            return self._send(200, "application/json", json.dumps(dict(ok=True, camera=S.cam_on, audio=S.mic_on)).encode())
        if path == "/api/energy" and _energy:
            act = body.get("action")
            if act == "reset":
                _energy.METER.reset()
            elif act == "assume":
                _energy.save_assumptions(body)
            elif act == "calibrate":
                if _energy.METER.cal_state.get("running"):
                    return self._send(400, "application/json", json.dumps(dict(ok=False, error="already running")).encode())
                threading.Thread(target=run_calibration, args=(body.get("which", "active"),), daemon=True).start()
            return self._send(200, "application/json", json.dumps(dict(ok=True)).encode())
        if path == "/api/vlm":
            try:
                import vlm_agent
            except Exception:
                return self._send(404, "application/json", json.dumps(dict(ok=False, error="vlm_agent not installed")).encode())
            if body.get("action") == "restart":
                ok, msg = vlm_agent.restart()
                return self._send(200 if ok else 400, "application/json", json.dumps(dict(ok=ok, message=msg)).encode())
            pid = body.get("profile")
            ok, msg = vlm_agent.switch(pid)
            if ok and Handler.link:
                apply_profile_to_board(pid)
            return self._send(200 if ok else 400, "application/json", json.dumps(dict(ok=ok, message=msg)).encode())
        if path == "/api/reset" and Handler.link:
            ok = Handler.link.send_cfg(reset=1)
            S.history.clear()
            return self._send(200, "application/json", json.dumps(dict(ok=ok)).encode())
        if path == "/api/drop":
            try:
                n = int(body.get("n"))
            except (TypeError, ValueError):
                return self._send(400, "text/plain", b"n must be an integer")
            S.drop_n = max(0, min(1000, n))
            return self._send(200, "application/json", json.dumps(dict(ok=True, drop_n=S.drop_n)).encode())
        if path == "/api/clear":
            # reset the detector background on the board and delete every saved event (event_NNNN folders only)
            ok = Handler.link.send_cfg(reset=1) if Handler.link else False
            S.history.clear()
            removed = 0
            try:
                for n in os.listdir(Handler.events_dir):
                    d = os.path.join(Handler.events_dir, n)
                    if n.startswith("event_") and os.path.isdir(d) and not os.path.islink(d):
                        shutil.rmtree(d)
                        removed += 1
            except OSError:
                pass
            S.events_rx = 0
            return self._send(200, "application/json", json.dumps(dict(ok=ok, removed=removed)).encode())
        self._send(404, "text/plain", b"not found")

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/v2", "/v2/"):          # experimental copy of the dashboard: edit ui/index_v2.html, reload; same API and data as "/"
            return self._send(200, "text/html; charset=utf-8", open(os.path.join(UI_DIR, "index_v2.html"), "rb").read())
        if path in ("/", "/index.html"):
            return self._send(200, "text/html; charset=utf-8", open(os.path.join(UI_DIR, "index.html"), "rb").read())
        if path == "/live.mjpg":
            return self._mjpeg("live")
        if path == "/board.mjpg":
            return self._mjpeg("board")
        if path == "/api/status":
            return self._send(200, "application/json", json.dumps(status()).encode())
        if path == "/api/vlm":
            try:
                import vlm_agent
                return self._send(200, "application/json", json.dumps(vlm_agent.profiles_status()).encode())
            except Exception:
                return self._send(200, "application/json", json.dumps(dict(profiles=[], active=None, state="vlm_agent not installed")).encode())
        if path == "/api/energy":
            if not _energy:
                return self._send(200, "application/json", json.dumps(dict(error="energy module not installed")).encode())
            try:
                import vlm_agent
                pid = vlm_agent.status().get("profile") or "qwen3vl_rgb"
            except Exception:
                pid = "qwen3vl_rgb"
            return self._send(200, "application/json", json.dumps(_energy.summary_json(pid)).encode())
        if path == "/api/events":
            return self._send(200, "application/json", json.dumps(list_events(self.events_dir, limit=int((parse_qs(urlparse(self.path).query).get("limit") or ["8"])[0]))).encode())
        if path.startswith("/events/"):
            parts = path[len("/events/"):].split("/")
            if len(parts) == 2 and all(p and ".." not in p and "/" not in p for p in parts) and parts[1].endswith((".jpg", ".wav")):
                fp = os.path.join(self.events_dir, parts[0], parts[1])
                if os.path.isfile(fp):
                    return self._send(200, "image/jpeg" if parts[1].endswith(".jpg") else "audio/wav", open(fp, "rb").read())
        self._send(404, "text/plain", b"not found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="192.168.7.2")
    ap.add_argument("--no-board", action="store_true", help="camera panel only; do not connect to the board")
    ap.add_argument("--device", type=int, default=2)
    ap.add_argument("--keep-every", type=int, default=5)
    ap.add_argument("--ir-device", type=int, default=4, help="IR camera /dev/videoN (GREY 480x480); -1 = off")
    ap.add_argument("--drop", type=int, default=0, help="frames dropped after each frame sent to the board (0 = send all)")
    ap.add_argument("--ir-keep-every", type=int, default=5)
    ap.add_argument("--mic", default="plughw:2,0", help="ALSA capture device for the microphone; '' = off")
    ap.add_argument("--synthetic", action="store_true", help="moving-block test pattern instead of the camera")
    ap.add_argument("--events", default=os.path.join(ROOT, "events"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    Handler.events_dir = a.events
    link = None if a.no_board else BoardLink(a.board, proto.PORT_FRAMES)
    Handler.link = link
    S.drop_n = max(0, a.drop)
    if link:
        threading.Thread(target=event_loop, args=(a.board, a.events), daemon=True).start()
        if a.ir_device >= 0 and not a.synthetic:
            threading.Thread(target=ir_loop, args=(a.ir_device, a.ir_keep_every, link), daemon=True).start()
        if a.mic and not a.synthetic:
            threading.Thread(target=mic_loop, args=(a.mic, link), daemon=True).start()
    threading.Thread(target=gpu_loop, daemon=True).start()
    threading.Thread(target=yolo_an.preload, daemon=True).start()
    threading.Thread(target=profile_sync_loop, daemon=True).start()
    if _energy:
        _energy.start(cam_fps=lambda: S.cam_fps, mic_on=lambda: S.mic_on and not S.mic_err)
    try:
        import vlm_agent
        vlm_agent.start()
    except Exception as e:
        print("vlm_agent not started:", repr(e), flush=True)
    threading.Thread(target=camera_loop, args=(a.device, a.keep_every, link, a.synthetic), daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print(f"dashboard on http://{a.host}:{a.port}  (board: {'off' if a.no_board else a.board}, camera: {'synthetic' if a.synthetic else '/dev/video%d' % a.device})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
