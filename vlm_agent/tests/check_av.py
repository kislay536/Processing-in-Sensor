"""Checks for the LFM3-Omni RGB+audio profile and the profile switch (needs tests/_step3_H and _step3_E from tests/step3_audio.py).
Run from the project root with the dashboard stopped:  .venv/bin/python -m vlm_agent.tests.check_av
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np

from vlm_agent import agent, server

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name, info, flush=True)


def gpu_mem():
    return float(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).split()[0])


def first_event(tag):
    import glob
    d = sorted(glob.glob(f"{ROOT}/tests/_step3_{tag}/event_*"))[0]
    return d, json.load(open(d + "/meta.json"))


def variant(src, meta, samples=None, drop_audio=False):
    d = tempfile.mkdtemp(prefix="avchk_")
    for f in os.listdir(src):
        if f.endswith(".jpg"):
            shutil.copy(f"{src}/{f}", d)
    m = copy.deepcopy(meta)
    if drop_audio:
        m["audio"] = None
    elif samples is not None:
        with wave.open(f"{d}/audio.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(samples.astype(np.int16).tobytes())
        m["audio"] = dict(m["audio"], n_samples=len(samples), duration_s=len(samples) / 16000, complete=True)
    else:
        shutil.copy(f"{src}/audio.wav", d)
    return d, m


def speech_clip(n):
    p = "/usr/share/sounds/alsa/Front_Center.wav"
    with wave.open(p) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64)
        ch, sr = w.getnchannels(), w.getframerate()
    if ch > 1:
        raw = raw.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        raw = np.interp(np.arange(0, len(raw), sr / 16000), np.arange(len(raw)), raw)
    out = np.random.default_rng(3).normal(0, 12, n)
    out[16000:16000 + len(raw)] += raw[: max(0, n - 16000)] * 1.0
    return out


def main():
    mem0 = gpu_mem()
    server.start()
    ok = server.wait_ready(300)
    check("server loaded", ok, f"{server.STATE['profile']} {server.STATE['state']}")
    t = time.time()
    r, msg = server.switch("lfm3_omni_av")
    check("switch -> lfm3_omni_av accepted", r, msg)
    time.sleep(1)
    check("loaded after switch", server.wait_ready(400) and server.STATE["profile"] == "lfm3_omni_av", f"{round(time.time() - t, 1)} s, mem {gpu_mem()} MiB (before {mem0})")
    dH, mH = first_event("H")
    dE, mE = first_event("E")
    # 1. real video + audio chunk
    rep = agent.analyze_chunk(dH, mH, baseline={})
    check("rgb_audio completed, audio processed", rep["effective_mode"] == "rgb_audio" and rep["status"] == "completed" and rep["coverage"]["audio_processed"],
          f"{rep['status']} {rep['effective_mode']} {rep['runtime']['elapsed_seconds']} s, peak mem {rep['runtime']['peak_gpu_mem_used_mib']} MiB")
    print("   summary:", rep["summary"][:300])
    # 2. same video, audio replaced by silence -> different text, flagged near-silent
    n = mH["audio"]["n_samples"]
    dS, mS = variant(dH, mH, samples=np.random.default_rng(4).normal(0, 3, n))
    repS = agent.analyze_chunk(dS, mS, baseline={})
    check("silent audio: completed, text differs from the tone version", repS["status"] == "completed" and repS["summary"] != rep["summary"], repS["summary"][:200])
    # 3. missing audio is not silence
    dN, mN = variant(dH, mH, drop_audio=True)
    repN = agent.analyze_chunk(dN, mN, baseline={})
    check("missing audio: effective rgb, status partial", repN["effective_mode"] == "rgb" and repN["status"] == "partial" and not repN["coverage"]["audio_processed"], repN["status"])
    # 4. speech clip -> transcription mentions the words; tone/noise -> no words
    dP, mP = variant(dH, mH, samples=speech_clip(n))
    repP = agent.analyze_chunk(dP, mP, baseline={})
    sp = " ".join(x["text"] for x in repP["speech"]).lower()
    check("speech clip transcribed", "front" in sp or "center" in sp or "centre" in sp, repr(sp))
    check("tone burst gives no invented speech", not rep["speech"], repr(rep["speech"]))
    # 5. 30 s chunk -> windows + synthesis (frames repeated, audio looped)
    check("windows have audio of the same interval", all(w.get("audio_s") for w in rep["windows"]), [w.get("audio_s") for w in rep["windows"]])
    # 6. switch back to Qwen
    t = time.time()
    server.switch("qwen3vl_rgb")
    time.sleep(1)
    check("switch back to Qwen", server.wait_ready(400) and server.STATE["profile"] == "qwen3vl_rgb", f"{round(time.time() - t, 1)} s, mem {gpu_mem()} MiB")
    repQ = agent.analyze_chunk(dH, mH, baseline={})
    check("Qwen profile ignores audio (rgb)", repQ["effective_mode"] == "rgb" and repQ["status"] == "completed" and not repQ["coverage"]["audio_processed"], repQ["summary"][:120])
    for d in (dS, dN, dP):
        shutil.rmtree(d, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    server.stop()
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
