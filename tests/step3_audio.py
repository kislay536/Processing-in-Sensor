#!/usr/bin/env python3
"""Step 3 end-to-end on the real board: audio-change trigger (video OR audio) and audio streamed back with the chunk.
Synthetic scene + synthetic microphone from the relay; receiver = GPU side. Needs the dashboard stopped (one :5001 client).

E  static video, sound 12-16 s, trig_mode=1  -> exactly 1 chunk, trigger cause 'audio', audio.wav covers the chunk (>= sound length)
F  same input, trig_mode=0                   -> no chunk (the audio change is ignored)
G  video motion 12-16 s, silent audio, mode 1 -> 1 chunk, cause 'video', audio present but quiet (silence is not missing audio)
H  motion 12-16 s + sound 14-18 s, mode 1     -> one chunk, cause 'video+audio'
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import wave

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
ap = argparse.ArgumentParser(); ap.add_argument("--board", default="192.168.7.2")
a = ap.parse_args()


def run(name, seconds, motion_at, motion_dur, sound_at, sound_dur, cfg):
    out = os.path.join(ROOT, "tests", "_step3_" + name)
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    recv = subprocess.Popen([PY, f"{ROOT}/gpu/receiver.py", "--board", a.board, "--out", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    cmd = [PY, f"{ROOT}/relay/relay.py", "--board", a.board, "--source", "synthetic", "--seconds", str(seconds), "--keep-every", "5",
           "--motion-at", str(motion_at), "--motion-dur", str(motion_dur), "--period", "100", "--audio-synth",
           "--sound-at", str(sound_at), "--sound-dur", str(sound_dur), "--cfg"] + cfg
    r = subprocess.run(cmd, capture_output=True, text=True)
    time.sleep(6)
    recv.terminate(); recv.wait()
    metas = [json.load(open(f"{out}/{d}/meta.json")) for d in sorted(os.listdir(out)) if d.startswith("event_") and os.path.exists(f"{out}/{d}/meta.json")]
    print(f"[{name}] {r.stdout.strip().splitlines()[-1]}")
    for m in metas:
        au = m.get("audio")
        print(f"   chunk {m['event_id']}: {m['n_frames']} frames {m['duration_s']} s, cause {m.get('trigger_cause')}, ended: {m['end_reason']}, "
              f"audio {au and (au['n_blocks'], au['duration_s'], au['rms'], au['complete'])}")
    return out, metas


def wav_ok(out, m):
    au = m["audio"]
    with wave.open(f"{out}/event_{m['event_id']:04d}/audio.wav") as w:
        return w.getframerate() == 16000 and w.getnchannels() == 1 and w.getnframes() == au["n_samples"]


C = ["ctx_period_s=0", "trig_mode=1"]
res = []
out, E = run("E", 40, 999, 1, 12, 4, C)
ok = len(E) == 1 and E[0]["trigger_cause"] == "audio" and E[0]["audio"] and E[0]["audio"]["complete"] and E[0]["audio"]["duration_s"] >= 4.0 and wav_ok(out, E[0])
print(f"   E: {'PASS' if ok else 'FAIL'}"); res.append(ok)
out, F = run("F", 40, 999, 1, 12, 4, ["ctx_period_s=0", "trig_mode=0"])
ok = len(F) == 0
print(f"   F: {len(F)} chunk(s) -> {'PASS' if ok else 'FAIL'}"); res.append(ok)
out, G = run("G", 40, 12, 4, 999, 1, C)
ok = len(G) == 1 and G[0]["trigger_cause"] == "video" and G[0]["audio"] and G[0]["audio"]["rms"] < 100 and G[0]["audio"]["complete"]
print(f"   G: {'PASS' if ok else 'FAIL'}"); res.append(ok)
out, H = run("H", 40, 12, 4, 14, 4, C)
ok = len(H) == 1 and H[0]["trigger_cause"] == "video+audio" and H[0]["audio"] and H[0]["audio"]["complete"]
print(f"   H: {'PASS' if ok else 'FAIL'}"); res.append(ok)
subprocess.run([PY, f"{ROOT}/relay/relay.py", "--board", a.board, "--source", "synthetic", "--seconds", "1", "--cfg", "max_chunk_s=30"], capture_output=True)   # defaults back
print("PASS" if all(res) else "FAIL", f"{sum(res)}/{len(res)}")
sys.exit(0 if all(res) else 1)
