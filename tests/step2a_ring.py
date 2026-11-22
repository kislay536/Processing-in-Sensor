#!/usr/bin/env python3
"""Step 2a: laptop -> Zedboard over Ethernet, 1 of every 5 frames, 60-slot DDR ring, CRC verified, readback.

  .venv/bin/python tests/step2a_ring.py [--seconds 300] [--source camera|synthetic] [--board 192.168.7.2]

Runs relay/relay.py (30 fps camera -> keep 1 in 5) for --seconds, then asks the board for its counters and reads back all
60 ring slots (the board recomputes CRC32 from DDR). Pass criteria:
  1. board frame counter == frames the relay sent;   2. board crc_err == 0, bad_len == 0, fid_gaps == 0
  3. ring wrapped (frames sent > 60);                4. the 60 slots hold exactly the last 60 frames sent
  5. every slot: DDR-recomputed CRC == CRC received == relay's CRC for that frame, and the payload's CRC matches too
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from common import proto


def query(board, slot):
    s = socket.create_connection((board, proto.PORT_FRAMES), timeout=10)
    s.sendall(proto.REQ_MSG.pack(proto.MAGIC_REQ, slot, 0))
    if slot == proto.REQ_STATS:
        magic, frames, crc_err, bad_len, gaps, last_fid, nbytes = proto.STS_MSG.unpack(proto.recv_exact(s, proto.STS_MSG.size))
        assert magic == proto.MAGIC_STS, magic
        s.close()
        return dict(frames_rx=frames, crc_err=crc_err, bad_len=bad_len, fid_gaps=gaps, last_fid=last_fid, bytes_rx=nbytes)
    magic, sl, fid, ln, crc_ddr, crc_rx = proto.RSP_HDR.unpack(proto.recv_exact(s, proto.RSP_HDR.size))
    assert magic == proto.MAGIC_RSP, magic
    payload = proto.recv_exact(s, ln)
    s.close()
    return dict(slot=sl, fid=fid, crc_ddr=crc_ddr, crc_rx=crc_rx, crc_payload=zlib.crc32(payload), len=ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="192.168.7.2")
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--source", default="camera", choices=["camera", "synthetic"])
    ap.add_argument("--device", default="2")
    a = ap.parse_args()

    log = os.path.join(ROOT, "docs", "step2a_relay_log.jsonl")
    before = query(a.board, proto.REQ_STATS)
    print("board before:", before, flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "relay", "relay.py"), "--board", a.board, "--source", a.source,
                        "--device", a.device, "--keep-every", "5", "--seconds", str(a.seconds), "--log", log],
                       capture_output=True, text=True)
    wall = time.time() - t0
    print(r.stdout.strip(), r.stderr.strip()[-300:], flush=True)
    time.sleep(1.0)
    sent = [json.loads(l) for l in open(log)]
    st = query(a.board, proto.REQ_STATS)
    print("board after:", st, flush=True)

    n_new = st["frames_rx"] - before["frames_rx"]
    last60 = sent[-proto.NSLOT:]
    expect_slot = {}                                     # slot index = (board frame counter) % 60; the counter was `before` at start
    for i, e in enumerate(sent):
        expect_slot[(before["frames_rx"] + i) % proto.NSLOT] = e
    bad_slots, checked = [], 0
    for sl in range(proto.NSLOT):
        if sl not in expect_slot:
            continue
        got = query(a.board, sl)
        e = expect_slot[sl]
        ok = (got["fid"] == e["fid"] and got["crc_ddr"] == e["crc"] and got["crc_rx"] == e["crc"] and got["crc_payload"] == e["crc"]
              and got["len"] == 614400)
        checked += 1
        if not ok:
            bad_slots.append((sl, got, e))
    fps_sent = len(sent) / wall
    checks = {
        f"board counted every frame the relay sent ({n_new} vs {len(sent)})": n_new == len(sent),
        "crc_err == 0": st["crc_err"] - before["crc_err"] == 0,
        "bad_len == 0": st["bad_len"] - before["bad_len"] == 0,
        "no frame-id gaps": st["fid_gaps"] - before["fid_gaps"] == 0,
        f"ring wrapped ({len(sent)} frames > {proto.NSLOT})": len(sent) > proto.NSLOT,
        f"all {proto.NSLOT} slots read back and match ({checked} checked, {len(bad_slots)} bad)": checked == proto.NSLOT and not bad_slots,
    }
    res = dict(seconds=round(wall, 1), frames_sent=len(sent), mean_fps_to_board=round(fps_sent, 2), board_before=before,
               board_after=st, slots_checked=checked, bad_slots=[(s, g, e) for s, g, e in bad_slots][:3], checks=checks)
    json.dump(res, open(os.path.join(ROOT, "docs", "step2a_result.json"), "w"), indent=1, default=str)
    print(f"sent {len(sent)} frames in {wall:.0f} s = {fps_sent:.2f} fps to the board")
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    for sl, g, e in bad_slots[:3]:
        print("  bad slot", sl, g, e)
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
