import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from common import proto
from board_sim.detector import Detector, Params, downscale_5x5, y_plane


def yuyv(y):
    f = np.empty((480, 640, 2), np.uint8); f[..., 0] = y; f[..., 1] = 128
    return f.tobytes()


class FakeSock:
    def __init__(self, data): self.data, self.pos = data, 0
    def recv(self, n):
        c = self.data[self.pos:self.pos + n]; self.pos += len(c); return c


class TestProto(unittest.TestCase):
    def test_header_sizes(self):
        self.assertEqual(proto.FRM_HDR.size, 32)
        self.assertEqual((proto.REQ_MSG.size, proto.RSP_HDR.size, proto.STS_MSG.size), (12, 24, 32))
        self.assertEqual(proto.EVT_HDR.size, 24)
        self.assertEqual(proto.EVT_FRAME.size, 16)
        self.assertEqual(proto.STA_MSG.size, 32)

    def test_frame_roundtrip(self):
        p = os.urandom(1000)
        s = FakeSock(proto.pack_frame(7, 123456789, 640, 480, p))
        self.assertEqual(proto.read_frame(s), (7, 123456789, 640, 480, 1, p))

    def test_event_roundtrip(self):
        frames = [(i, 1000 + i, os.urandom(50)) for i in range(3)]
        s = FakeSock(proto.pack_event(2, 1, 150, 800, 640, 480, frames))
        kind, m = proto.read_message(s)
        self.assertEqual(kind, "EVT")
        self.assertEqual((m["event_id"], m["trigger_frame_id"], m["motion_x1000"], m["person_x1000"]), (2, 1, 150, 800))
        self.assertEqual(m["frames"], frames)


class TestDetector(unittest.TestCase):
    def scene(self, block=False):
        y = np.full((480, 640), 110, np.uint8)
        if block: y[100:300, 100:300] = 240
        return yuyv(y)

    def test_downscale_shape_and_value(self):
        self.assertEqual(downscale_5x5(y_plane(self.scene())).shape, (96, 128))
        self.assertTrue((downscale_5x5(y_plane(self.scene())) == 110).all())

    def test_static_scene_never_fires(self):
        d = Detector(Params())
        self.assertFalse(any(d.step(self.scene())[1] for _ in range(60)))

    def test_motion_fires_once_then_cooldown(self):
        d = Detector(Params())
        for _ in range(20): d.step(self.scene())
        fires = [d.step(self.scene(True))[1] for _ in range(10)]
        self.assertEqual(sum(fires), 1)


class TestEndToEnd(unittest.TestCase):
    def test_synthetic_event_reaches_gpu_stage(self):
        out = tempfile.mkdtemp()
        py = sys.executable
        board = subprocess.Popen([py, "-u", f"{ROOT}/board_sim/board_sim.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(1)
        gpu = subprocess.Popen([py, "-u", f"{ROOT}/gpu/receiver.py", "--out", out, "--max-events", "1"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        relay = subprocess.Popen([py, "-u", f"{ROOT}/relay/relay.py", "--source", "synthetic", "--fps", "10",
                                  "--seconds", "40", "--motion-at", "6", "--motion-dur", "5", "--period", "60"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            gpu.wait(timeout=60)
            self.assertEqual(gpu.returncode, 0, gpu.stdout.read())
            ev = os.path.join(out, "event_0001")
            meta = json.load(open(os.path.join(ev, "meta.json")))
            self.assertGreater(meta["n_frames"], 10)
            self.assertTrue(os.path.exists(os.path.join(ev, "report.md")))
        finally:
            for p in (relay, gpu, board):
                p.kill()
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
