#!/usr/bin/env python3
"""DEV SCAFFOLDING, not the demo: Python stand-in for the Zedboard firmware.

Same protocol and same detector maths as the board (see detector.py, the golden model). It exists so the
relay and the GPU stage can be tested end to end before the board/cable are available.

  python3 board_sim/board_sim.py [--host 127.0.0.1]
"""
import argparse
import collections
import os
import queue
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import proto
from board_sim.detector import Params
from board_sim.gate import Gate


class Board:
    def __init__(self, host, params: Params, quiet=False):
        self.host, self.p, self.quiet = host, params, quiet
        self.gate = Gate(params)
        self.stats = dict(frames_in=0, triggers=0, bytes_in=0, bytes_out=0, motion=0, person=0)
        self.out_q = queue.Queue()
        self.gpu_conns = []
        self.lock = threading.Lock()
        self.event_id = 0
        self.stop = threading.Event()

    def log(self, *a):
        if not self.quiet:
            print("[board]", *a, flush=True)

    # ---- GPU side (port 5001) ----
    def serve_gpu(self):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, proto.PORT_EVENTS)); s.listen(4)
        threading.Thread(target=self.sender, daemon=True).start()
        while not self.stop.is_set():
            s.settimeout(0.5)
            try:
                c, addr = s.accept()
            except socket.timeout:
                continue
            self.log("GPU stage connected", addr)
            with self.lock:
                self.gpu_conns.append(c)

    def sender(self):
        last_sta = 0
        while not self.stop.is_set():
            try:
                msg = self.out_q.get(timeout=0.5)
            except queue.Empty:
                msg = None
            now = time.time()
            if msg is None and now - last_sta > 1.0:
                st = self.stats
                msg = proto.STA_MSG.pack(proto.MAGIC_STA, st["frames_in"], st["triggers"], st["bytes_in"],
                                         st["bytes_out"], st["motion"], st["person"])
                last_sta = now
                is_evt = False
            else:
                is_evt = msg is not None
            if msg is None:
                continue
            with self.lock:
                conns = list(self.gpu_conns)
            if not conns:
                if is_evt:
                    self.out_q.put(msg); time.sleep(0.2)   # hold events until a GPU stage connects
                continue
            for c in conns:
                try:
                    c.sendall(msg)
                    if is_evt:
                        self.stats["bytes_out"] += len(msg)
                except OSError:
                    with self.lock:
                        if c in self.gpu_conns:
                            self.gpu_conns.remove(c)

    # ---- frame side (port 5000) ----
    def serve_frames(self):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, proto.PORT_FRAMES)); s.listen(1)
        self.log(f"listening: frames {proto.PORT_FRAMES}, events {proto.PORT_EVENTS}")
        while not self.stop.is_set():
            s.settimeout(0.5)
            try:
                c, addr = s.accept()
            except socket.timeout:
                continue
            self.log("relay connected", addr)
            try:
                while not self.stop.is_set():
                    fid, ts, w, h, fmt, payload = proto.read_frame(c)
                    self.on_frame(fid, ts, w, h, payload)
            except (ConnectionError, OSError):
                self.log("relay disconnected")

    def on_frame(self, fid, ts, w, h, payload):
        st = self.stats
        st["frames_in"] += 1
        st["bytes_in"] += len(payload) + proto.FRM_HDR.size
        motion, ev = self.gate.feed(fid, ts, payload)
        st["motion"] = motion
        st["triggers"] = self.gate.triggers
        if ev:
            self.event_id += 1
            self.out_q.put(proto.pack_event(self.event_id, ev["trigger_frame_id"], ev["motion_x1000"], 0, w, h, ev["frames"]))
            self.log(f"event {self.event_id}: trigger frame {ev['trigger_frame_id']}, {len(ev['frames'])} frames "
                     f"({sum(len(f[2]) for f in ev['frames'])/1e6:.1f} MB) queued")

    def run(self):
        threading.Thread(target=self.serve_gpu, daemon=True).start()
        self.serve_frames()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    try:
        Board(a.host, Params()).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
