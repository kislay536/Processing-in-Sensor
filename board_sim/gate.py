"""Board-side gate: ring buffer + detector + trigger + pre/post-roll windowing. Pure logic, no sockets.

Shared by board_sim.py and the benchmark so both run exactly the same trigger behaviour.
"""
import collections
from board_sim.detector import Detector, Params


class Gate:
    def __init__(self, params: Params = None):
        self.p = params or Params()
        self.det = Detector(self.p)
        self.ring = collections.deque(maxlen=self.p.n_pre + self.p.n_post + 40)  # (fid, ts, payload)
        self.pending = None          # [trigger_fid, remaining_post, motion]
        self.last_motion = 0
        self.triggers = 0

    def feed(self, fid, ts, payload):
        """Feed one frame. Returns (motion_x1000, event_or_None).
        event = dict(trigger_frame_id, motion_x1000, frames=[(fid, ts, payload), ...])"""
        self.ring.append((fid, ts, payload))
        motion, fire = self.det.step(payload)
        self.last_motion = motion
        if self.pending:
            self.pending[1] -= 1
            if self.pending[1] <= 0:
                return motion, self._flush()
        elif fire:
            self.triggers += 1
            self.pending = [fid, self.p.n_post, motion]
            if self.p.n_post == 0:
                return motion, self._flush()
        return motion, None

    def _flush(self):
        tfid, _, motion = self.pending
        self.pending = None
        frames = list(self.ring)
        idx = next(i for i, f in enumerate(frames) if f[0] == tfid)
        lo = max(0, idx - self.p.n_pre)
        return dict(trigger_frame_id=tfid, motion_x1000=motion, frames=frames[lo: idx + 1 + self.p.n_post])
