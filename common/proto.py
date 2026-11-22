"""PiSe wire protocol (TCP, little-endian). Mirrors board/sw/proto.h and docs/protocol.md.

Port 5000: relay -> board   FRM1 frames
Port 5001: board -> GPU     EVT1 events (pre/post-event frame window) and STA1 stats
"""
import socket
import struct

PORT_FRAMES = 5000
PORT_EVENTS = 5001

MAGIC_FRM = b"FRM1"
MAGIC_EVT = b"EVT1"
MAGIC_STA = b"STA1"

FMT_YUYV = 1        # colour 640x480, 614400 B
FMT_GREY = 2        # IR 480x480 GREY, 230400 B
FMT_PCM16 = 3       # microphone, 512 x int16 = 1024 B
FRAME_BYTES = {FMT_YUYV: 614400, FMT_GREY: 230400, FMT_PCM16: 1024}

# magic, frame_id, ts_us, w, h, fmt, pad[3], len, crc32(payload)
FRM_HDR = struct.Struct("<4sIQHHB3xII")
# Step 2a board diagnostics (same port as FRM1):
#   REQ1 (laptop->board): magic, slot (0..59 = read that ring slot; 0xFFFFFFFF = read stats), reserved
#   RSP1 (board->laptop): magic, slot, frame_id, len, crc32 recomputed by the board from DDR, crc32 received  + payload
#   STS1 (board->laptop): magic, frames_rx, crc_err, bad_len, fid_gaps, last_fid, bytes_rx
MAGIC_REQ, MAGIC_RSP, MAGIC_STS = b"REQ1", b"RSP1", b"STS1"
REQ_MSG = struct.Struct("<4sII")
RSP_HDR = struct.Struct("<4s5I")
STS_MSG = struct.Struct("<4s5IQ")
REQ_STATS = 0xFFFFFFFF
NSLOT = 60
REQ_DET = 0xFFFFFFFE
# CFG1 (laptop->board, same connection): magic + NPARAM x u32, applied immediately by the firmware (board/sw/src/main.c `params`)
MAGIC_CFG, MAGIC_DET = b"CFG1", b"DET1"
NPARAM = 32
PARAM_NAMES = ["pix_min", "var_init", "var_min", "var_max", "var_shift", "min_cells", "persist_frames", "freeze_frames", "illum_en",
               "illum_min", "cell_req", "global_limit", "resid_limit", "pre", "hang", "max_chunk_s", "ir_thr", "ir_shift", "reset", "ctx_period_s", "ctx_frames",
               "trig_mode", "aud_ratio_x10", "aud_persist", "aud_floor_rms"]
PARAM_DEFAULTS = dict(pix_min=20, var_init=4, var_min=1, var_max=127, var_shift=1, min_cells=2, persist_frames=2, freeze_frames=3,
                      illum_en=1, illum_min=10, cell_req=16, global_limit=2457, resid_limit=204, pre=4, hang=6, max_chunk_s=30,
                      ir_thr=24, ir_shift=3, reset=0, ctx_period_s=60, ctx_frames=10,
                      trig_mode=0, aud_ratio_x10=40, aud_persist=3, aud_floor_rms=150)   # trig_mode 0 = video only, 1 = video OR audio
# DET1 (board->laptop): magic + 40 x u32 + 64 x u8 (8x8 cell counts) + 8 x u64 (audio band powers) + 32 x u32 (current params)
DET_MSG = struct.Struct("<4s40I64B8Q32I")
DET_FIELDS = ["col_frames", "crc_err", "last_fid", "fired", "reason", "score", "region_pass", "active_cells", "changed", "persistence",
              "ip_frames", "chunks_sent", "episodes_dropped", "event_state", "chunk_id", "onsets", "ir_frames", "ir_changed", "ir_score",
              "ir_ip_frames", "aud_blocks", "aud_ip_blocks", "aud_sumsq_lo", "aud_sumsq_hi", "gpu_client", "img_us", "fired_frames",
              "frames_sent", "frames_lost", "episode", "queue_depth",
              "aud_fired", "aud_rms", "aud_base_rms", "aud_onsets", "aud_sent", "aud_lost", "trig_cause", "reserved0", "reserved1"]
REASONS = ["warmup", "none", "change", "exposure_rebase", "global_hold", "global_rebase"]
EVENT_STATES = ["static (nothing sent)", "motion: streaming to GPU", "scene context burst"]
CHUNK_REASONS = ["motion ended", "max chunk length", "interrupted", "scene context"]
TRIG_CAUSES = {0: "none", 1: "video", 2: "audio", 3: "video+audio"}


def pack_cfg(**kw):
    vals = dict(PARAM_DEFAULTS); vals.update(kw)
    arr = [int(vals[n]) for n in PARAM_NAMES] + [0] * (NPARAM - len(PARAM_NAMES))
    return MAGIC_CFG + struct.pack(f"<{NPARAM}I", *arr)


def parse_det(buf: bytes) -> dict:
    v = DET_MSG.unpack(buf)
    d = dict(zip(DET_FIELDS, v[1:41]))
    d["cells"] = list(v[41:105])
    d["bands"] = list(v[105:113])
    d["params"] = dict(zip(PARAM_NAMES, v[113:113 + len(PARAM_NAMES)]))
    d["reason_name"] = REASONS[d["reason"]] if d["reason"] < len(REASONS) else str(d["reason"])
    d["event_state_name"] = EVENT_STATES[d["event_state"]] if d["event_state"] < len(EVENT_STATES) else "?"
    d["aud_sumsq"] = d["aud_sumsq_lo"] | (d["aud_sumsq_hi"] << 32)
    return d
# magic, event_id, trigger_frame_id, motion_x1000, person_x1000, n_frames, w, h, fmt, pad
EVT_HDR = struct.Struct("<4sIIHHHHHBx")
# frame_id, ts_us, len
EVT_FRAME = struct.Struct("<IQI")
# Motion-gated streaming (board -> GPU, :5001). EVF1 = one colour frame with its timestamp, EVE1 = end of a chunk.
#   EVF1: magic, seg, episode, chunk, seq, flags (bit0 first in chunk, bit1 pre-roll, bit2 scene-context frame), fid, ts_us, w, h, fmt, changed_px, len  + payload
#   EVE1: magic, seg, episode, chunk, n_frames, reason (0 motion ended, 1 max chunk length, 2 interrupted, 3 scene context), first_ts_us, last_ts_us, n_audio_blocks
#   EVA1: magic, seg, episode, chunk, first_seq, n_blocks, flags, first_ts_us, len, pad  + n_blocks x 1024 B PCM16 (16 kHz mono, 512 samples = 32 ms per block)
#   EVF1 flags also: bit3 video detector firing on this frame, bit4 audio detector firing
MAGIC_EVF, MAGIC_EVE, MAGIC_EVA = b"EVF1", b"EVE1", b"EVA1"
AUDIO_RATE, AUDIO_BLOCK_SAMPLES = 16000, 512
EVF_HDR = struct.Struct("<4sIIIIIIQHHBxHI")
EVE_MSG = struct.Struct("<4sIIIIIQQI")
EVA_HDR = struct.Struct("<4sIIIIIIQI8x")
# magic, frames_in, triggers, bytes_in, bytes_out, motion_x1000, person_x1000
STA_MSG = struct.Struct("<4sIIQQHH")


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(65536, n - len(buf)))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return bytes(buf)


def pack_frame(frame_id, ts_us, w, h, payload, fmt=FMT_YUYV):   # fmt selects the board stream: 1 colour, 2 IR, 3 audio
    import zlib
    return FRM_HDR.pack(MAGIC_FRM, frame_id, ts_us, w, h, fmt, len(payload), zlib.crc32(payload)) + payload


def read_frame(sock):
    """Returns (frame_id, ts_us, w, h, fmt, payload)."""
    import zlib
    magic, fid, ts, w, h, fmt, ln, crc = FRM_HDR.unpack(recv_exact(sock, FRM_HDR.size))
    if magic != MAGIC_FRM:
        raise ValueError(f"bad frame magic {magic!r}")
    payload = recv_exact(sock, ln)
    if zlib.crc32(payload) != crc:
        raise ValueError(f"frame {fid}: crc mismatch")
    return fid, ts, w, h, fmt, payload


def pack_event(event_id, trigger_frame_id, motion, person, w, h, frames, fmt=FMT_YUYV):
    """frames: list of (frame_id, ts_us, payload)."""
    out = [EVT_HDR.pack(MAGIC_EVT, event_id, trigger_frame_id, motion, person, len(frames), w, h, fmt)]
    for fid, ts, payload in frames:
        out.append(EVT_FRAME.pack(fid, ts, len(payload)))
        out.append(payload)
    return b"".join(out)


def read_message(sock):
    """Reads one board->GPU message. Returns ('STA', dict) or ('EVT', dict)."""
    magic = recv_exact(sock, 4)
    if magic == MAGIC_STA:
        rest = recv_exact(sock, STA_MSG.size - 4)
        _, fin, trig, bin_, bout, mo, pe = STA_MSG.unpack(magic + rest)
        return "STA", dict(frames_in=fin, triggers=trig, bytes_in=bin_, bytes_out=bout,
                           motion_x1000=mo, person_x1000=pe)
    if magic == MAGIC_EVF:
        _, seg, ep, ch, seq, fl, fid, ts, w, h, fmt, changed, ln = EVF_HDR.unpack(magic + recv_exact(sock, EVF_HDR.size - 4))
        return "EVF", dict(seg=seg, episode=ep, chunk=ch, seq=seq, flags=fl, fid=fid, ts_us=ts, w=w, h=h, fmt=fmt, changed=changed,
                           payload=recv_exact(sock, ln))
    if magic == MAGIC_EVE:
        _, seg, ep, ch, n, rs, t0, t1, na = EVE_MSG.unpack(magic + recv_exact(sock, EVE_MSG.size - 4))
        return "EVE", dict(seg=seg, episode=ep, chunk=ch, n_frames=n, reason=rs, first_ts_us=t0, last_ts_us=t1, n_audio=na)
    if magic == MAGIC_EVA:
        _, seg, ep, ch, seq, nb, fl, ts, ln = EVA_HDR.unpack(magic + recv_exact(sock, EVA_HDR.size - 4))
        return "EVA", dict(seg=seg, episode=ep, chunk=ch, seq=seq, n_blocks=nb, flags=fl, ts_us=ts, payload=recv_exact(sock, ln))
    if magic == MAGIC_EVT:
        rest = recv_exact(sock, EVT_HDR.size - 4)
        _, eid, tfid, mo, pe, n, w, h, fmt = EVT_HDR.unpack(magic + rest)
        frames = []
        for _ in range(n):
            fid, ts, ln = EVT_FRAME.unpack(recv_exact(sock, EVT_FRAME.size))
            frames.append((fid, ts, recv_exact(sock, ln)))
        return "EVT", dict(event_id=eid, trigger_frame_id=tfid, motion_x1000=mo, person_x1000=pe,
                           w=w, h=h, fmt=fmt, frames=frames)
    raise ValueError(f"bad message magic {magic!r}")
