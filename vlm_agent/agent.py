"""Scene-report agent. Modes: rgb (Qwen profile), rgb_audio (LFM3-Omni profile: frames + the audio of the same interval); thermal is defined but not fed by the board.

analyze_chunk(event_dir, meta, baseline) -> report dict (README section 8 shape):
  validate frames -> 4 s windows, <= 4 frames each (evenly spaced), long edge 336 px -> one stateless request per window
  -> text-only synthesis if more than one window -> JSON + Markdown. Failures shorten the window / shrink frames, never
  fall back to a text-only guess.
"""
import base64
import datetime as dt
import io
import os
import subprocess
import threading
import time

import cv2
import numpy as np

from . import profiles, prompts, server

QUANT = "Q4_K_M"
AUDIO_RATE = 16000

# last description of a "scene context" chunk, handed to later motion chunks as the "scene before"
BASELINE = dict(text="", ts_us=0)


class _VramPeak:
    """Polls nvidia-smi while a chunk is analysed. Reports total GPU memory in use (all processes), not just this model."""
    def __init__(self):
        self.peak, self._run = None, False

    def _loop(self):
        while self._run:
            try:
                v = float(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True, timeout=2).split()[0])
                self.peak = v if self.peak is None else max(self.peak, v)
            except Exception:
                pass
            time.sleep(0.5)

    def __enter__(self):
        self._run = True; self._t = threading.Thread(target=self._loop, daemon=True); self._t.start(); return self

    def __exit__(self, *a):
        self._run = False; self._t.join(timeout=2)


def _clock(ts_us):
    d = dt.datetime.fromtimestamp(ts_us / 1e6)
    return d.strftime("%H:%M:%S") + f".{d.microsecond // 1000:03d}"


def _encode(path, long_edge):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"cannot decode {os.path.basename(path)}")
    h, w = img.shape[:2]
    s = long_edge / max(h, w)
    if s < 1:
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode(), img.shape[1], img.shape[0]


def validate(event_dir, meta):
    """Returns (frames, issues). Frames: list of dict(file, ts_us) with decodable files and non-decreasing timestamps."""
    issues, out, last = [], [], None
    for f in meta.get("frames", []):
        p = os.path.join(event_dir, f["file"])
        if not os.path.exists(p):
            issues.append(f"missing file {f['file']}"); continue
        if last is not None and f["ts_us"] < last:
            issues.append(f"timestamp order violated at {f['file']}"); continue
        last = f["ts_us"]
        out.append(dict(file=f["file"], path=p, ts_us=f["ts_us"]))
    return out, issues


def make_windows(frames, window_s=4.0, max_frames=4):
    t0 = frames[0]["ts_us"]
    wins, w = [], 0
    while True:
        a, b = t0 + int(w * window_s * 1e6), t0 + int((w + 1) * window_s * 1e6)
        inw = [f for f in frames if a <= f["ts_us"] < b]
        if not inw and a > frames[-1]["ts_us"]:
            break
        if inw:
            k = min(max_frames, len(inw))
            idx = [round(i * (len(inw) - 1) / max(k - 1, 1)) for i in range(k)] if k > 1 else [0]
            wins.append(dict(id=f"w{len(wins):03d}", start_s=(a - t0) / 1e6, end_s=min((b - t0) / 1e6, (frames[-1]["ts_us"] - t0) / 1e6 + 1e-3),
                             frames=[inw[i] for i in sorted(set(idx))], n_in_window=len(inw)))
        w += 1
    return wins


def load_audio(event_dir, meta):
    """The chunk's audio.wav as (int16 samples, start_ts_us) or None (None = no audio at all, which is different from silence)."""
    a = meta.get("audio")
    if not a:
        return None
    import wave
    try:
        with wave.open(os.path.join(event_dir, a["file"])) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    except Exception:
        return None
    return (x, a["start_ts_us"]) if len(x) else None


def slice_audio(aud, start_us, end_us):
    """Samples covering exactly [start_us, end_us) on the frame clock, or None when less than half of it is covered."""
    x, t0 = aud
    a = int(round((start_us - t0) * AUDIO_RATE / 1e6)); b = int(round((end_us - t0) * AUDIO_RATE / 1e6))
    lo, hi = max(a, 0), min(b, len(x))
    if b <= a or hi - lo < 0.5 * (b - a):
        return None
    return x[lo:hi]


def _rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0


def _wav_b64(x):
    import wave
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(AUDIO_RATE); w.writeframes(x.astype(np.int16).tobytes())
    return base64.b64encode(bio.getvalue()).decode()


def _window_request(win, t0, mode, is_context, baseline, long_edge, n_frames, audio=None):
    fr = win["frames"]
    if n_frames < len(fr):                                    # fallback: fewer frames, still evenly spread
        keep = sorted({round(i * (len(fr) - 1) / max(n_frames - 1, 1)) for i in range(n_frames)}) if n_frames > 1 else [0]
        fr = [fr[i] for i in keep]
    quiz = prompts.QUIZ and mode in prompts.QUIZ_PROMPTS
    live = prompts.LIVE and not quiz and mode in prompts.LIVE_PROMPTS
    text = prompts.QUIZ_PROMPTS[mode] if quiz else (prompts.LIVE_PROMPTS[mode] if live else prompts.PROMPTS[mode])
    text += f"\nThe {len(fr)} frames below are in chronological order, taken between +{win['start_s']:.1f} s and +{win['end_s']:.1f} s of a clip that started at {_clock(t0)}."
    if mode == "rgb_audio" and audio is not None:
        lvl = _rms(audio)
        text += (f"\nThe audio clip after the frames covers the same interval ({len(audio) / AUDIO_RATE:.1f} s, 16 kHz mono). "
                 + ("Its level is near-silent." if lvl < profiles.SILENT_RMS else f"Its RMS level is {lvl:.0f} (int16 units)."))
    if quiz or live:
        pass
    elif is_context:
        text += "\n" + prompts.CONTEXT_NOTE
    elif baseline.get("text"):
        ago = f"{max(0, (t0 - baseline['ts_us']) / 1e6):.0f} s before this clip"
        text += "\n" + prompts.BASELINE_NOTE.format(ago=ago, text=baseline["text"])
    content = [{"type": "text", "text": text}]
    dims = []
    for f in fr:
        url, w, h = _encode(f["path"], long_edge)
        dims.append((w, h))
        content.append({"type": "text", "text": f"Frame at +{(f['ts_us'] - t0) / 1e6:.2f} s ({_clock(f['ts_us'])}):"})
        content.append({"type": "image_url", "image_url": {"url": url}})
    if mode == "rgb_audio" and audio is not None:
        content.append({"type": "input_audio", "input_audio": {"data": _wav_b64(audio), "format": "wav"}})
    system = prompts.QUIZ_SYSTEM if quiz else (prompts.LIVE_SYSTEM if live else (prompts.SYSTEM_AV if mode == "rgb_audio" else prompts.SYSTEM))
    return [{"role": "system", "content": system}, {"role": "user", "content": content}], fr, dims


def _infer_window(win, t0, mode, is_context, baseline, long_edge, audio=None):
    """Bounded fallback ladder: full -> half the frames -> half the frames at 224 px (audio stays whole). Returns (text, used) or raises."""
    n0 = len(win["frames"])
    ladder = [(n0, long_edge), (max(1, n0 // 2), long_edge), (max(1, n0 // 2), 224)]
    last = None
    for n, edge in ladder:
        try:
            msgs, fr, dims = _window_request(win, t0, mode, is_context, baseline, edge, n, audio)
            text, usage = server.chat(msgs, **(dict(max_tokens=prompts.LIVE_MAX_TOKENS) if prompts.LIVE and not prompts.QUIZ else {}))
            if not text:
                raise RuntimeError("empty model output")
            return text, dict(frames=len(fr), long_edge=edge, size=list(dims[0]) if dims else None, prompt_tokens=usage.get("prompt_tokens"),
                              frame_files=[f["file"] for f in fr], timestamps_s=[round((f["ts_us"] - t0) / 1e6, 2) for f in fr],
                              audio_s=round(len(audio) / AUDIO_RATE, 2) if audio is not None else None,
                              audio_rms=round(_rms(audio), 1) if audio is not None else None)
        except Exception as e:
            last = e
    raise RuntimeError(f"window failed after fallbacks: {last!r}")


def _speechlike(x):
    """Cheap gate before the ASR pass: among the loud 20 ms frames, speech has a strongly varying level (syllables), a tone / hum /
    steady noise does not. ASR models invent words ("Thank you.") on non-speech audio, so they only see clips that pass this gate."""
    n = 320
    k = len(x) // n
    if k < 10:
        return False
    e = np.sqrt((x[: k * n].astype(np.float64).reshape(k, n) ** 2).mean(axis=1)) + 1.0
    act = e[e > max(3.0 * np.percentile(e, 10), 0.5 * profiles.ASR_GATE_RMS)]
    if len(act) < 10:                                         # < 0.2 s of loud audio
        return False
    return bool(act.std() / act.mean() >= profiles.SPEECH_CV)


def _speech(audio):
    """Optional speech pass (LFM ASR prompt). Returns quoted text only when it contains words; noise/tones give ''. Always uncertain."""
    if audio is None or _rms(audio) < profiles.ASR_GATE_RMS or not _speechlike(audio):
        return ""
    try:
        text, _ = server.chat([{"role": "system", "content": prompts.ASR},
                               {"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": _wav_b64(audio), "format": "wav"}}]}], max_tokens=96)
    except Exception:
        return ""
    t = text.strip()
    letters = sum(ch.isalpha() for ch in t)
    return t if letters >= 3 else ""


def _quiz_answer(obs):
    import re
    lines = []
    for key in ("Red", "Hello"):
        seen = [re.search(key + r"\s*:\s*(yes|no)", o["description"], re.I) for o in obs]
        seen = [m.group(1).lower() for m in seen if m]
        if seen:
            ans = "yes" in seen
            if key == "Hello" and not any(o.get("speechlike") for o in obs):
                ans = False                                    # the small model says "yes" to anything: no speech-like audio, no yes
            lines.append(f"{key}: {'yes' if ans else 'no'}")
        elif key == "Red" or any(o.get("mode") == "rgb_audio" for o in obs):
            lines.append(f"{key}: unclear ({obs[0]['description'][:60]!r})")
    return "\n".join(lines)


def _synthesize(observations, coverage_note):
    lines = [f"[{o['window_id']}] +{o['interval_s'][0]:.1f}-{o['interval_s'][1]:.1f} s: {o['description']}"
             + (f" (automatic transcript, may be wrong: \"{o['speech']}\")" if o.get("speech") else "") for o in observations]
    text = prompts.SYNTHESIS + "\n\nWindow observations (chronological):\n" + "\n".join(lines) + "\n\nCoverage: " + coverage_note
    out, _ = server.chat([{"role": "system", "content": prompts.SYSTEM}, {"role": "user", "content": text}], max_tokens=320)
    return out


def _analyze_audio_only(event_dir, meta, rep, t_start):
    """Camera off: the chunk is only audio. One request (audio, up to 20 s) plus the speech pass when the audio sounds like speech."""
    aud = load_audio(event_dir, meta)
    rep["effective_mode"] = "audio"
    rep["limitations"] = ["Camera was off: audio-only chunk, nothing visual was analysed.",
                          "Small general model (2B, 4-bit); descriptions can be wrong, speech transcription is automatic and uncertain."]
    if aud is None:
        rep["error"] = "audio file missing or empty"
        rep["runtime"]["elapsed_seconds"] = round(time.time() - t_start, 2)
        return rep
    x = aud[0][-20 * AUDIO_RATE:]
    with _VramPeak() as vp, server.GPU_LOCK:
        server.STATE["busy"] = True
        try:
            content = [{"type": "text", "text": (prompts.LIVE_AUDIO if prompts.LIVE else prompts.AUDIO_ONLY) + f"\nThe clip is {len(x) / AUDIO_RATE:.1f} s long, 16 kHz mono, RMS level {_rms(x):.0f} (int16 units)."},
                       {"type": "input_audio", "input_audio": {"data": _wav_b64(x), "format": "wav"}}]
            text, usage = server.chat([{"role": "system", "content": prompts.SYSTEM_AUDIO}, {"role": "user", "content": content}], max_tokens=prompts.LIVE_MAX_TOKENS if prompts.LIVE else 200)
            rep["summary"] = text.strip()
            sp = "" if prompts.LIVE else _speech(x)
            if sp:
                rep["speech"] = [dict(interval_s=[0.0, round(len(x) / AUDIO_RATE, 2)], text=sp)]
            rep["timeline"] = []
            rep["status"] = "completed"
        except Exception as e:
            rep["error"] = f"audio request failed: {e!r}"
        finally:
            server.STATE["busy"] = False
    rep["runtime"].update(elapsed_seconds=round(time.time() - t_start, 2), peak_gpu_mem_used_mib=vp.peak if hasattr(vp, "peak") else None)
    return rep


def analyze_chunk(event_dir, meta, baseline=None, mode=None):
    t_start = time.time()
    baseline = BASELINE if baseline is None else baseline
    prof = server.profile()
    mode = mode or prof["mode"]
    is_context = meta.get("kind") == "context"
    rep = dict(request_id=f"event_{meta.get('event_id'):04d}" if isinstance(meta.get("event_id"), int) else str(meta.get("event_id")),
               requested_mode=mode, effective_mode=mode, status="failed", profile=prof["id"], profile_label=prof["label"], model=prof["hf_repo"],
               quantization=QUANT, prompt_version=prompts.PROMPT_VERSION, kind=meta.get("kind", "motion"), trigger_cause=meta.get("trigger_cause"),
               summary="", speech=[], timeline=[], limitations=[], coverage={}, windows=[],
               runtime=dict(cpu_offload_used=False, peak_gpu_mem_used_mib=None, elapsed_seconds=None))
    lim = ["Small general model (2B, 4-bit); descriptions can be wrong, details may be missed.",
           "Frames are passed as ordered, timestamp-labelled images (multi-image approximation, not native video).",
           "Sampled at most %d frames per %.0f s window; brief actions between samples can be missed." % (prof["max_frames"], prof["window_s"]),
           "Timestamps are laptop-clock times when each frame / audio block was read (30-60 ms uncertainty between audio and video)."]
    if mode not in ("rgb", "rgb_audio"):
        rep["limitations"] = ["mode %s is not wired to the board yet" % mode]
        rep["error"] = f"mode {mode} not implemented"
        return rep
    frames, issues = validate(event_dir, meta)
    rep["limitations"] = lim + issues
    if not frames and meta.get("kind") == "audio" and meta.get("audio"):
        return _analyze_audio_only(event_dir, meta, rep, t_start)
    if not frames:
        rep["error"] = "no usable frames: " + ("; ".join(issues) or "chunk is empty")
        rep["runtime"]["elapsed_seconds"] = round(time.time() - t_start, 2)
        return rep
    aud = None
    if mode == "rgb_audio":
        aud = load_audio(event_dir, meta)
        if aud is None:
            rep["effective_mode"] = "rgb"
            rep["limitations"].append("audio missing for this chunk: analysed as RGB only (a missing track is not the same as silence)")
        elif meta.get("audio", {}).get("complete") is False:
            rep["limitations"].append("audio incomplete: fewer blocks arrived than the board sent")
    else:
        if meta.get("audio"):
            rep["limitations"].append("this profile is RGB only: the chunk's audio was not used")
    emode = rep["effective_mode"]
    t0 = frames[0]["ts_us"]
    wins = make_windows(frames, prof["window_s"], prof["max_frames"])
    obs, failed, processed, audio_missing = [], [], [], []
    with _VramPeak() as vp, server.GPU_LOCK:
        server.STATE["busy"] = True
        try:
            for w in wins:
                try:
                    a_us, b_us = t0 + int(w["start_s"] * 1e6), t0 + int(w["end_s"] * 1e6)
                    asl = slice_audio(aud, a_us, b_us) if aud is not None else None
                    wmode = emode
                    if emode == "rgb_audio" and asl is None:
                        wmode = "rgb"
                        audio_missing.append([round(w["start_s"], 2), round(w["end_s"], 2)])
                    text, used = _infer_window(w, t0, wmode, is_context, baseline, prof["long_edge"], asl)
                    o = dict(window_id=w["id"], interval_s=[round(w["start_s"], 2), round(w["end_s"], 2)], description=text, mode=wmode, **used)
                    if prompts.QUIZ:
                        o["speechlike"] = bool(asl is not None and _rms(asl) >= profiles.ASR_GATE_RMS and _speechlike(asl))
                    if prof["asr"] and asl is not None and not prompts.QUIZ and not prompts.LIVE:
                        o["speech"] = _speech(asl)
                    obs.append(o)
                    processed.append(o["interval_s"])
                except Exception as e:
                    failed.append([round(w["start_s"], 2), round(w["end_s"], 2)])
                    rep["limitations"].append(f"{w['id']} failed: {e}")
            if prompts.QUIZ and obs:
                rep["summary"] = _quiz_answer(obs)             # fixed two-line answer: yes if any window said yes
            elif prompts.LIVE and obs:
                rep["summary"] = " ".join(o["description"].strip() for o in obs)      # one sentence per window, no synthesis call
            elif len(obs) == 1:
                rep["summary"] = obs[0]["description"]
            elif obs:
                try:
                    rep["summary"] = _synthesize(obs, f"processed {processed}; missing {failed}; windows without audio {audio_missing}")
                except Exception as e:
                    rep["summary"] = " ".join(o["description"] for o in obs)
                    rep["limitations"].append(f"synthesis failed ({e!r}); window descriptions concatenated")
        finally:
            server.STATE["busy"] = False
    rep["timeline"] = [dict(window_id=o["window_id"], interval_s=o["interval_s"], description=o["description"], speech=o.get("speech", ""),
                            clock=[_clock(t0 + int(o["interval_s"][0] * 1e6)), _clock(t0 + int(o["interval_s"][1] * 1e6))]) for o in obs]
    rep["speech"] = [dict(interval_s=o["interval_s"], text=o["speech"]) for o in obs if o.get("speech")]
    rep["windows"] = [{k: v for k, v in o.items() if k not in ("description", "speech")} for o in obs]
    audio_used = [o["interval_s"] for o in obs if o.get("audio_s") is not None]
    if rep["speech"]:
        rep["limitations"].append("speech text is an automatic transcription by the same small model and may be wrong")
    rep["coverage"] = dict(chunk_start_ts_us=t0, chunk_start_clock=_clock(t0), requested_interval_s=[0.0, round((frames[-1]["ts_us"] - t0) / 1e6, 2)],
                           processed_intervals_s=processed, missing_intervals_s=failed,
                           sampled_frame_timestamps_s=[t for o in obs for t in o["timestamps_s"]], audio_processed=bool(audio_used),
                           audio_intervals_s=audio_used, missing_audio_intervals_s=audio_missing if aud is not None else ([[0.0, round((frames[-1]["ts_us"] - t0) / 1e6, 2)]] if mode == "rgb_audio" else []),
                           frames_in_chunk=len(meta.get("frames", [])), frames_used=len(frames))
    partial = bool(failed or issues or (mode == "rgb_audio" and (aud is None or audio_missing)))
    rep["status"] = "failed" if not obs else ("partial" if partial else "completed")
    if not obs:
        rep["error"] = "no window could be analysed"
    rep["runtime"].update(peak_gpu_mem_used_mib=vp.peak, elapsed_seconds=round(time.time() - t_start, 2))
    if rep["status"] != "failed" and is_context:
        BASELINE.update(text=rep["summary"], ts_us=frames[-1]["ts_us"])
    return rep


def to_markdown(rep):
    L = [f"# Scene report {rep.get('request_id')} ({rep.get('kind')}, {rep.get('profile_label')}) - {rep.get('status')}", "",
         rep.get("summary") or rep.get("error", ""), "", "## Timeline"]
    for t in rep.get("timeline", []):
        L.append(f"- +{t['interval_s'][0]:.1f}-{t['interval_s'][1]:.1f} s ({t['clock'][0]}-{t['clock'][1]}): {t['description']}")
    if rep.get("speech"):
        L += ["", "## Speech (automatic transcription, uncertain)"] + [f"- +{x['interval_s'][0]:.1f}-{x['interval_s'][1]:.1f} s: \"{x['text']}\"" for x in rep["speech"]]
    c = rep.get("coverage", {})
    L += ["", "## Coverage", f"- trigger: {rep.get('trigger_cause')}; mode {rep.get('effective_mode')} (requested {rep.get('requested_mode')})",
          f"- processed {c.get('processed_intervals_s')} of {c.get('requested_interval_s')} s; missing {c.get('missing_intervals_s')}",
          f"- sampled frames at +{c.get('sampled_frame_timestamps_s')} s; audio processed: {c.get('audio_processed')}", "", "## Limitations"]
    L += [f"- {x}" for x in rep.get("limitations", [])]
    r = rep.get("runtime", {})
    L += ["", f"Runtime: {r.get('elapsed_seconds')} s, peak GPU memory in use {r.get('peak_gpu_mem_used_mib')} MiB (all processes), prompt {rep.get('prompt_version')}."]
    return "\n".join(L)
