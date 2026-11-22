"""GPU-side assembler for the board's motion-gated stream (EVF1 frames + EVE1 chunk ends, common/proto.py).

Each frame is decoded and written to events/event_<seg>/f<fid>.jpg as soon as it arrives (a 30 s chunk is never held in RAM);
the chunk's meta.json is written when EVE1 arrives (or when the connection is lost: reason 'interrupted').
"""
import json
import os
import time
import wave

import cv2
import numpy as np

from common import proto


class ChunkAssembler:
    def __init__(self, out_root):
        self.out_root = out_root
        self.cur = {}                                     # board seg -> dict(dir, frames, bytes)
        # The board restarts its chunk numbering at 1 after every firmware reload, so the laptop numbers events itself
        # (a reused number would mix frames of two different events in one folder).
        ids = [int(n[6:]) for n in os.listdir(out_root) if n.startswith("event_") and n[6:].isdigit()] if os.path.isdir(out_root) else []
        self.next_id = max(ids, default=0) + 1

    def _dir(self, lid):
        return os.path.join(self.out_root, f"event_{lid:04d}")

    def _chunk(self, m):
        c = self.cur.get(m["seg"])
        if c is None:
            lid = self.next_id
            self.next_id += 1
            d = self._dir(lid)
            os.makedirs(d, exist_ok=True)
            c = self.cur[m["seg"]] = dict(lid=lid, dir=d, frames=[], bytes=0, episode=m["episode"], chunk=m["chunk"], w=640, h=480)
        return c

    def on_audio(self, m):
        """EVA1: append PCM16 blocks to audio.wav; blocks are contiguous, the bundle timestamps give the clock."""
        c = self._chunk(m)
        a = c.setdefault("audio", dict(blocks=0, t0=None, t1=None, sumsq=0.0, n=0, bundles=[], wav=None))
        if a["wav"] is None:
            a["wav"] = wave.open(os.path.join(c["dir"], "audio.wav"), "wb")
            a["wav"].setnchannels(1); a["wav"].setsampwidth(2); a["wav"].setframerate(proto.AUDIO_RATE)
        a["wav"].writeframes(m["payload"])
        x = np.frombuffer(m["payload"], np.int16).astype(np.float64)
        a["sumsq"] += float((x * x).sum()); a["n"] += len(x)
        a["blocks"] += m["n_blocks"]
        if a["t0"] is None:
            a["t0"] = m["ts_us"]
        a["t1"] = m["ts_us"] + int(m["n_blocks"] * proto.AUDIO_BLOCK_SAMPLES * 1e6 / proto.AUDIO_RATE)
        a["bundles"].append([m["seq"], m["n_blocks"], m["ts_us"]])

    def on_frame(self, m):
        c = self._chunk(m)
        c["w"], c["h"] = m["w"], m["h"]
        yuyv = np.frombuffer(m["payload"], np.uint8).reshape(m["h"], m["w"], 2)
        bgr = cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUY2)
        name = f"f{m['fid']:06d}.jpg"
        cv2.imwrite(os.path.join(c["dir"], name), bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        c["frames"].append(dict(frame_id=m["fid"], ts_us=m["ts_us"], file=name, changed_px=m["changed"], preroll=bool(m["flags"] & 2), context=bool(m["flags"] & 4), seq=m["seq"], cause=(1 if m["flags"] & 8 else 0) | (2 if m["flags"] & 16 else 0)))
        c["bytes"] += len(m["payload"])

    def _finish(self, seg, reason_name, first_ts=None, last_ts=None, n_audio=None):
        c = self.cur.pop(seg, None)
        if not c or not c["frames"]:
            return None
        fr = c["frames"]
        trig = next((f for f in fr if not f["preroll"]), fr[0])
        t0, t1 = fr[0]["ts_us"], fr[-1]["ts_us"]
        kind = "context" if fr[0].get("context") else "motion"
        cause = 0
        for f in fr:
            cause |= f.get("cause", 0)
        a = c.get("audio")
        audio = None
        if a and a["wav"] is not None:
            a["wav"].close()
            audio = dict(file="audio.wav", sample_rate=proto.AUDIO_RATE, n_blocks=a["blocks"], n_samples=a["n"], start_ts_us=a["t0"], end_ts_us=a["t1"],
                         duration_s=round(a["n"] / proto.AUDIO_RATE, 3), rms=round((a["sumsq"] / max(a["n"], 1)) ** 0.5, 1),
                         expected_blocks=n_audio, complete=(n_audio is None or a["blocks"] == n_audio), bundles=a["bundles"])
        meta = dict(kind=kind, trigger_cause=proto.TRIG_CAUSES[cause], audio=audio, event_id=c["lid"], board_seg=seg, episode=c["episode"], chunk=c["chunk"], end_reason=reason_name,
                    trigger_frame_id=trig["frame_id"], trigger_ts_us=trig["ts_us"],
                    motion_x1000=max(f["changed_px"] for f in fr) * 1000 // 4096, person_x1000=0,
                    n_frames=len(fr), start_ts_us=t0, end_ts_us=t1, duration_s=round((t1 - t0) / 1e6, 3),
                    fps=round((len(fr) - 1) / max((t1 - t0) / 1e6, 1e-6), 2) if len(fr) > 1 else 0,
                    frames=fr, bytes_received=c["bytes"], received_at=time.time())
        with open(os.path.join(c["dir"], "meta.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        return c["dir"], meta

    def on_end(self, m):
        name = proto.CHUNK_REASONS[m["reason"]] if m["reason"] < len(proto.CHUNK_REASONS) else str(m["reason"])
        return self._finish(m["seg"], name, n_audio=m.get("n_audio"))

    def flush_incomplete(self):
        """Connection lost: finish whatever chunks were in flight."""
        out = []
        for seg in list(self.cur):
            r = self._finish(seg, "interrupted")
            if r:
                out.append(r)
        return out
