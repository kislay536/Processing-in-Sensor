import json, sys, wave
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, "sensors")
from golden import N_BLOCK, ChangeDetector, goertzel_bands_fast
sess, out = sys.argv[1], sys.argv[2]
ph = json.load(open(f"{sess}/phases.json")); t_zero = ph[0]["start"] - 15
def series(small, thr=24, sh=3):
    cd = ChangeDetector(pix_thresh=thr, bg_shift=sh); n = small.shape[1]*small.shape[2]
    return np.array([1000*cd.step(f, reset=(i==0))[0]//n for i, f in enumerate(small)])
rgb = np.load(f"{sess}/rgb_y128x96.npy"); rts = np.load(f"{sess}/rgb_ts.npy") - t_zero
ir = np.load(f"{sess}/ir_y96x96.npy"); its = np.load(f"{sess}/ir_ts.npy") - t_zero
w = wave.open(f"{sess}/audio.wav"); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64)
t0 = json.load(open(f"{sess}/audio_t0.json"))["t0"] - t_zero
nb = len(x)//N_BLOCK; rms = np.sqrt((x[:nb*N_BLOCK].reshape(nb, N_BLOCK)**2).mean(1)); bts = t0 + (np.arange(nb)+.5)*N_BLOCK/16000
fig, ax = plt.subplots(5, 1, figsize=(13, 9), sharex=True)
ax[0].plot(rts, series(rgb), lw=.8); ax[0].set_ylabel("colour: changed\n‰ pixels")
ax[1].plot(its, series(ir, 12), lw=.8, c="tab:red"); ax[1].set_ylabel("IR: changed\n‰ pixels")
ax[2].plot(bts, rms, lw=.5, c="tab:green"); ax[2].set_ylabel("mic RMS"); ax[2].set_yscale("log")
ax[3].plot(rts, rgb.mean((1,2)), lw=.8, label="colour mean"); ax[3].plot(its, ir.mean((1,2)), lw=.8, c="tab:red", label="IR mean"); ax[3].legend(loc="upper right"); ax[3].set_ylabel("mean brightness")
ax[4].plot(bts, 20*np.log10(rms+1), lw=.5, c="tab:green"); ax[4].set_ylabel("mic level dB")
for a in ax:
    for p in ph:
        a.axvspan(p["start"]-t_zero, p["cue_end"]-t_zero, color="0.85")
        a.axvline(p["start"]-t_zero, c="k", lw=.5)
for p in ph: ax[0].text(p["cue_end"]-t_zero, ax[0].get_ylim()[1]*0.9, p["name"], fontsize=8)
ax[-1].set_xlabel("seconds since cameras started (grey = spoken instruction)")
plt.tight_layout(); plt.savefig(out, dpi=80)
