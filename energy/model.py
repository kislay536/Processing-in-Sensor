"""Measurement + analytical model.

MEASURED (FPGA-gated pipeline, what the dashboard really does):
  * GPU power / utilisation / memory / clocks: sampled at 10 Hz (pynvml, fallback nvidia-smi), energy = integral of power.
  * Traffic to the GPU: bytes that actually arrive on the board->GPU connection (:5001).
GPU-ONLY BASELINE ("the model runs continuously, whether or not anything is detected"):
  * calibrate(): the FPGA path is paused and the live analysis is run 10 times back to back; the GPU trace (power, utilisation, ...) of each call
    is cut out and averaged ELEMENT-WISE across the calls -> one average profile of ONE call.
  * baseline = that profile repeated call after call over the whole timeline (wavy, never idle), so it stays above the FPGA-gated line.
ASSUMED (cannot be measured here, editable in the dashboard): energy per bit of the GPU-facing link, FPGA board power.
Not counted in either case (identical): camera, microphone, laptop CPU. The camera->FPGA hop is local to the capture node.
"""
import bisect
import json
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CAL_FILE = os.path.join(HERE, "calibration.json")
ASSUME_FILE = os.path.join(HERE, "assumptions.json")
FRAME_BYTES = 640 * 480 * 2
AUDIO_BYTES_PER_S = 16000 * 2
SAMPLE_S = 0.1            # GPU sampling interval
DEFAULT_ASSUME = dict(link_nj_per_bit=1.0, board_w=None, board_w_extra=1.5)   # board_w None -> Vivado on-chip estimate + extra




def _vivado_onchip_w():
    try:
        for line in open(os.path.join(HERE, "vivado_power.rpt")):
            if "Total On-Chip Power" in line:
                return float(line.split("|")[2].strip())
    except (OSError, ValueError, IndexError):
        pass
    return None


def load_assumptions():
    a = dict(DEFAULT_ASSUME)
    try:
        a.update(json.load(open(ASSUME_FILE)))
    except (OSError, ValueError):
        pass
    v = _vivado_onchip_w()
    a["vivado_onchip_w"] = v
    a["board_w_used"] = a["board_w"] if a.get("board_w") is not None else ((v if v is not None else 2.0) + a["board_w_extra"])
    return a


def save_assumptions(upd):
    a = {k: v for k, v in load_assumptions().items() if k in DEFAULT_ASSUME}
    for k in DEFAULT_ASSUME:
        if k in upd:
            a[k] = None if upd[k] in (None, "") else float(upd[k])
    json.dump(a, open(ASSUME_FILE, "w"))
    return load_assumptions()


def load_calibration():
    try:
        return json.load(open(CAL_FILE))
    except (OSError, ValueError):
        return {}



class Meter:
    def __init__(self):
        # (t, power_w, util, mem_mib, camera_fps, mem_util, sm_clock_mhz, temp_c, src_on), 10 Hz, 1 h
        self.samples = deque(maxlen=36000)
        self.rx = {}                                     # second -> bytes received from the board
        self.t_reset = time.time()
        self.e_gpu_j = 0.0                               # measured GPU energy since reset
        self.rx_bytes = 0
        self.windows = 0                                 # analysed windows since reset (for the model check)
        self.analysis_s = 0.0
        self.cam_fps = lambda: 0.0
        self.mic_on = lambda: True
        self._last = None
        self.paused = False                              # set while the isolated calibration owns the GPU
        self.cal_state = dict(running=False, text="", progress=0.0)
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.t_reset = time.time(); self.e_gpu_j = 0.0; self.rx_bytes = 0; self.windows = 0; self.analysis_s = 0.0; self.rx.clear()

    def add_rx(self, nbytes):
        sec = int(time.time())
        with self.lock:
            self.rx[sec] = self.rx.get(sec, 0) + nbytes
            self.rx_bytes += nbytes
            for k in [k for k in self.rx if k < sec - 3700]:
                del self.rx[k]

    def note_analysis(self, n_windows, seconds):
        with self.lock:
            self.windows += n_windows; self.analysis_s += seconds

    def _add(self, t, w, u, m, mu, clk, tmp):
        fps = float(self.cam_fps() or 0.0)
        src = 1 if (fps > 0 or self.mic_on()) else 0
        with self.lock:
            if self._last is not None:
                self.e_gpu_j += w * min(t - self._last[0], 2.0)
            self._last = (t, w)
            self.samples.append((t, w, u, m, fps, mu, clk, tmp, src))

    def _loop_nvml(self):
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        while True:
            t = time.time()
            u = pynvml.nvmlDeviceGetUtilizationRates(h)
            self._add(t, pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0, float(u.gpu), pynvml.nvmlDeviceGetMemoryInfo(h).used / 2 ** 20, float(u.memory),
                      float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)), float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)))
            time.sleep(SAMPLE_S)

    def _loop_smi(self):
        p = subprocess.Popen(["nvidia-smi", "--query-gpu=power.draw,utilization.gpu,memory.used,utilization.memory,clocks.sm,temperature.gpu",
                              "--format=csv,noheader,nounits", "-lms", "250"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in p.stdout:
            try:
                w, u, m, mu, clk, tmp = [float(x) for x in line.split(",")]
            except ValueError:
                continue
            self._add(time.time(), w, u, m, mu, clk, tmp)

    def _loop(self):
        use_nvml = True
        while True:
            try:
                (self._loop_nvml if use_nvml else self._loop_smi)()
            except Exception:
                use_nvml = False                          # pynvml missing / failing: fall back to nvidia-smi
            time.sleep(2)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def window(self, t0, t1):
        """Mean power / utilisation and energy (J) of the samples in [t0, t1]."""
        with self.lock:
            s = [x for x in self.samples if t0 <= x[0] <= t1]
        if len(s) < 2:
            return None
        e = sum(a[1] * min(b[0] - a[0], 2.0) for a, b in zip(s, s[1:]))
        return dict(power_w=sum(x[1] for x in s) / len(s), util=sum(x[2] for x in s) / len(s), energy_j=e, seconds=s[-1][0] - s[0][0], mem=max(x[3] for x in s))

    def trace(self, t0, t1):
        with self.lock:
            return [x for x in self.samples if t0 <= x[0] <= t1]


METER = Meter()


def start(cam_fps=None, mic_on=None):
    if cam_fps:
        METER.cam_fps = cam_fps
    if mic_on:
        METER.mic_on = mic_on
    METER.start()


# ---------------------------------------------------------------- isolated calibration: the 10-call average profile
def _bank(profile_mode, events_dir, n):
    """The n newest recorded real chunks that have frames (and audio for the audio profile); falls back to the synthetic test chunks."""
    import glob
    cands = []
    for d in sorted(glob.glob(os.path.join(events_dir, "event_*")), reverse=True)[:150]:
        try:
            m = json.load(open(os.path.join(d, "meta.json")))
        except (OSError, ValueError):
            continue
        if m.get("n_frames", 0) < 8 or m.get("kind") == "audio":
            continue
        if profile_mode == "rgb_audio" and not m.get("audio"):
            continue
        cands.append((d, m))
        if len(cands) >= n:
            break
    if not cands:
        for d in glob.glob(os.path.join(ROOT, "tests", "_step3_*", "event_*")):
            try:
                cands.append((d, json.load(open(os.path.join(d, "meta.json")))))
            except (OSError, ValueError):
                pass
    return cands


def _call_profile(calls, M=20):
    """calls: list of (t_start, t_next_start, samples). Element-wise average, over the calls, of the GPU trace of one call (call i runs from its start
    until the next call starts): every trace is interpolated onto the same M points over the call, then mean / std are taken point by point."""
    chans = dict(power=1, util=2, mem_mib=3, mem_util=5, sm_clock=6, temp=7)
    per = {k: [] for k in chans}
    raw = []
    for t0, t1, S in calls:
        ts = np.array([x[0] for x in S]); tt = t0 + np.arange(M) / M * (t1 - t0)
        for k, ix in chans.items():
            per[k].append(np.interp(tt, ts, [x[ix] for x in S]))
        inside = [x for x in S if t0 <= x[0] <= t1]
        raw.append(dict(d=round(t1 - t0, 3), t=[round(float(x[0] - t0), 3) for x in inside], power=[round(float(x[1]), 2) for x in inside], util=[round(float(x[2]), 1) for x in inside]))
    mean = {k: np.mean(np.vstack(v), axis=0) for k, v in per.items()}
    std = {k: np.std(np.vstack(v), axis=0) for k, v in per.items()}
    return mean, std, raw


def calibrate(profile_id, events_dir, n_calls=10):
    """GPU-only measurement: the FPGA path is paused and the live analysis (the resident model) is run n_calls times back to back on recorded chunks,
    whether or not anything happened in them. The GPU trace of each call is averaged element-wise into one average profile of a call."""
    from vlm_agent import agent, server
    from gpu.analyzers import run_cascade
    st = METER.cal_state
    prof = server.profile()
    bank = _bank(prof["mode"], events_dir, n_calls)
    if not bank:
        st.update(running=False, text="no recorded chunks to replay; wait for some events")
        return None
    tmp = tempfile.mkdtemp(prefix="calib_")
    saved_base = dict(agent.BASELINE)
    try:
        st.update(running=True, text="FPGA path paused; GPU-only calls…", progress=0.0)
        METER.paused = True
        work = []
        for i, (d, m) in enumerate(bank):               # copies: the real events are never touched
            dd = os.path.join(tmp, f"c{i}"); shutil.copytree(d, dd, ignore=shutil.ignore_patterns("det_*", "scene.json", "report.*"))
            work.append((dd, m))
        run = lambda k: run_cascade(work[k % len(work)][0], dict(work[k % len(work)][1], event_id=work[k % len(work)][1].get("event_id", 0)))
        with server.GPU_LOCK:
            pass
        run(0)                                         # warm-up, not counted
        starts = []
        for k in range(n_calls):
            st.update(text=f"GPU-only call {k + 1}/{n_calls}…", progress=0.1 + 0.85 * k / n_calls)
            starts.append(time.time()); run(k)
        t_end = time.time()
        time.sleep(0.4)
        periods = [b - a for a, b in zip(starts, starts[1:] + [t_end])]
        calls = [(a, a + p, METER.trace(a - 0.3, a + p + 0.3)) for a, p in zip(starts, periods)]
        if any(len(S) < 4 for _, _, S in calls):
            st.update(running=False, text="not enough GPU samples (pynvml / nvidia-smi?)"); return None
        mean, std, raw = _call_profile(calls)
        d = float(np.mean(periods)); M = len(mean["power"])
        tgrid = np.arange(M) / M * d
        P, U = mean["power"], mean["util"]
        chunk_dur = float(np.mean([float(m.get("duration_s") or 0) for _, m in bank])) or 1.0
        cal = dict(profile=profile_id, label=prof["label"], at=time.time(), n_calls=n_calls, bank_chunks=len(bank), d_mean=round(d, 3), d_std=round(float(np.std(periods)), 3),
                   mean_w=round(float(P.mean()), 2), mean_util=round(float(U.mean()), 1), peak_w=round(float(P.max()), 2), peak_util=round(float(U.max()), 1),
                   min_w=round(float(P.min()), 2), min_util=round(float(U.min()), 1), peak_mem_mib=round(float(mean["mem_mib"].max()), 0),
                   e_call_j=round(float(P.mean()) * d, 2), samples_per_call=round(float(np.mean([len(S) for _, _, S in calls])), 1), chunk_s_bank=round(chunk_dur, 2),
                   profile_curve=dict(t=[round(float(x), 3) for x in tgrid], **{k: [round(float(x), 2) for x in v] for k, v in mean.items()},
                                      **{k + "_std": [round(float(x), 2) for x in v] for k, v in std.items() if k in ("power", "util")}), calls=raw,
                   # keys used by the original dashboard's cards
                   idle_w=round(float(P.min()), 2), idle_util=round(float(U.min()), 1), active_w=round(float(P.mean()), 2), active_util=round(float(U.mean()), 1),
                   sat_w=round(float(P.max()), 2), sat_util=round(float(U.max()), 1), sat_mean_w=round(float(P.mean()), 2), sat_mean_util=round(float(U.mean()), 1),
                   busy_frac=1.0, run_s=round(t_end - starts[0], 1), windows=n_calls, video_s=round(chunk_dur * n_calls, 1), compute_s_per_video_s=round(d / chunk_dur, 3),
                   realtime_ok=d <= chunk_dur, energy_per_window_j=round(float(P.mean()) * d, 2), window_s=round(chunk_dur, 2))
        c = load_calibration(); c[profile_id] = cal
        json.dump(c, open(CAL_FILE, "w"), indent=1)
        st.update(running=False, text=f"done: {n_calls} calls, one call = {d:.2f} s, mean {cal['mean_w']} W / {cal['mean_util']}% util (peak {cal['peak_w']} W / {cal['peak_util']}%)", progress=1.0)
        return cal
    finally:
        agent.BASELINE.clear(); agent.BASELINE.update(saved_base)
        shutil.rmtree(tmp, ignore_errors=True)
        METER.paused = False
        METER.reset()          # the calibration run is not normal operation: restart the measured counters so it is not counted


# ---------------------------------------------------------------- baseline: the average one-call profile repeated back to back
def baseline_mbps(fps, mic=True):
    return (fps * FRAME_BYTES + (AUDIO_BYTES_PER_S if mic else 0)) * 8 / 1e6


def _base_at(cal, t):
    """GPU-only baseline at time t: the averaged call profile, repeated call after call (periodic in d_mean)."""
    pc = cal["profile_curve"]; d = cal["d_mean"]; x = t % d
    return float(np.interp(x, pc["t"], pc["power"], period=d)), float(np.interp(x, pc["t"], pc["util"], period=d))


def summary_json(active_profile, window_s=900.0, bin_s=5.0, fine_s=120.0, fine_bin=0.2):
    M = METER
    a = load_assumptions()
    cals = load_calibration()
    cal = cals.get(active_profile)
    cal = cal if cal and "profile_curve" in cal and "mean_w" in cal else None      # an older calibration format counts as not calibrated
    now = time.time()
    t0 = max(M.t_reset, now - window_s)
    with M.lock:
        samples = [s for s in M.samples if s[0] >= min(t0, now - fine_s)]
        rx = dict(M.rx)
        e_gpu = M.e_gpu_j; rx_bytes = M.rx_bytes; t_reset = M.t_reset; wins = M.windows
    el = max(now - t_reset, 1e-6)
    ts = [s[0] for s in samples]

    def slice_(b0, b1):
        return samples[bisect.bisect_left(ts, b0):bisect.bisect_left(ts, b1)]

    nb = max(1, int((now - t0) / bin_s)); series = []                       # 5 s bins: cumulative energy plot, original dashboard
    for i in range(nb):
        b0 = t0 + i * bin_s; b1 = b0 + bin_s
        ss = slice_(b0, b1)
        if not ss:
            continue
        fps = sum(s[4] for s in ss) / len(ss)
        rxb = sum(v for k, v in rx.items() if b0 <= k < b1)
        series.append(dict(t=b1, gpu_w=round(sum(s[1] for s in ss) / len(ss), 2), gpu_util=round(sum(s[2] for s in ss) / len(ss), 1),
                           rx_mbps=round(rxb * 8 / 1e6 / bin_s, 3), base_mbps=round(baseline_mbps(fps, M.mic_on()), 2),
                           base_w=cal["mean_w"] if cal else None, base_util=cal["mean_util"] if cal else None))
    fine = []                                                                # 0.2 s bins over the last 2 min: the wave of the repeated call profile
    for i in range(int(fine_s / fine_bin)):
        b0 = now - fine_s + i * fine_bin; b1 = b0 + fine_bin
        ss = slice_(b0, b1)
        if not ss:
            continue
        row = dict(t=round((b0 + b1) / 2, 2), gpu_w=round(sum(s[1] for s in ss) / len(ss), 2), gpu_util=round(sum(s[2] for s in ss) / len(ss), 1), base_w=None, base_util=None)
        if cal:
            w_, u_ = _base_at(cal, (b0 + b1) / 2); row.update(base_w=round(w_, 2), base_util=round(u_, 1))
        fine.append(row)
    fps_now = float(M.cam_fps() or 0.0)
    bits_fpga = rx_bytes * 8
    avg_fps = (sum(s[4] for s in samples) / len(samples)) if samples else fps_now
    bits_base = baseline_mbps(avg_fps, M.mic_on()) * 1e6 * el
    e_link = a["link_nj_per_bit"] * 1e-9
    e_board = a["board_w_used"] * el
    out = dict(t_reset=t_reset, elapsed_s=round(el, 1), assumptions=a, calibration={k: {kk: vv for kk, vv in v.items() if kk not in ("calls", "profile_curve")} for k, v in cals.items()},
               active_profile=active_profile, calibrated=bool(cal), calibrating=M.cal_state, series=series, fine=fine, now=now, cam_fps=round(fps_now, 1),
               fpga=dict(traffic_mb=round(rx_bytes / 1e6, 2), avg_mbps=round(bits_fpga / el / 1e6, 3), gpu_j=round(e_gpu, 1), gpu_avg_w=round(e_gpu / el, 2),
                         link_j=round(bits_fpga * e_link, 3), board_j=round(e_board, 1), total_j=round(e_gpu + bits_fpga * e_link + e_board, 1), windows=wins))
    if cal:
        e_gpu_b = cal["mean_w"] * el
        out["baseline"] = dict(traffic_mb=round(bits_base / 8e6, 1), avg_mbps=round(bits_base / el / 1e6, 2), gpu_j=round(e_gpu_b, 1), gpu_avg_w=cal["mean_w"], gpu_util=cal["mean_util"],
                               duty=1.0, realtime_ok=cal["realtime_ok"], link_j=round(bits_base * e_link, 2), total_j=round(e_gpu_b + bits_base * e_link, 1))
        out["profile"] = dict(curve=cal["profile_curve"], calls=cal["calls"], d_mean=cal["d_mean"], mean_w=cal["mean_w"], mean_util=cal["mean_util"])
    else:
        out["baseline"] = None
    return out
