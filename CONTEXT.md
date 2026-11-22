# PiSe (formerly EventCam): full project context (read this first)

Written 2026-11-21 evening, during LauzHack 2026 (Nov 21-22). Everything below is what was built, measured and decided in the previous Claude Code session. Numbers are measured unless marked *(estimate)* or *(unverified)*. Directory: `/home/kislay/Documents/lauzhack/eventcam` (all paths below are relative to it unless absolute). **Do not touch `/home/kislay/Documents/lauzhack/flagship/`** (a separate project; only its Vivado board files, `ps7_init`, and XSA were borrowed read-only).

## 1. What the user is building and why

Hackathon challenges: **Logitech "intelligent eyes and ears"** (a Logitech LVNext camera as an edge sensor) + **AXA "frugal use of multimodal AI"**. The user's idea, "EventCam" (now named PiSe): an event-driven pipeline where cheap always-on detectors run on an FPGA and only wake the expensive GPU model when something happens.

Physical set-up (cannot place the FPGA on the camera, so the laptop relays):

```
LVNext camera (colour + IR + mic)  --USB-->  laptop (DUMB RELAY, no analysis)  --Ethernet-->  Zedboard (Zynq-7020)
Zedboard: keeps rolling caches in DDR, runs cheap detectors in the PL (FPGA fabric) -> trigger ->
          sends the cached window back over Ethernet -> laptop RTX 3050 (4 GB) runs a model on it
```

The user wants **honest pass/fail reporting after each step** ("tell me what works and what not"), steps tested one at a time. They are at a live hackathon, time matters.

### The pivot history (important to understand current direction)
1. Original request: camera -> laptop at 30 fps lowest resolution (Step 1); 1-in-5 frames to FPGA, **60-frame rolling cache in DDR**, **face detector in the PL**, trigger sends cache to GPU (Step 2).
2. Steps 1 and 2a were done and passed (see section 4). The face-detector path (2b/2c) was started and **parked**: a tiny CNN generalised poorly from one person's data; a pretrained YuNet teacher + public data helped only partly (section 6).
3. **Current direction (user's own idea, approved):** instead of a face CNN, use **cheap mathematical detectors on all three sensor streams at once**: frame-change on the colour camera, frame-change on the IR camera, and **frequency-band energy on the microphone**; fuse them; on trigger pass the window to the GPU, which runs a vision-language model ("Nemotron type") to describe/act. The user explicitly asked to get the **RTL (FPGA fabric) version of these detectors working**, which is done and verified (section 5).

## 2. Current status at a glance

| Item | Status |
|---|---|
| Step 1: camera -> laptop at 30 fps, 640x480 | PASS in MJPEG; raw YUYV FAILS the strict criterion (29.09 fps, ~3% camera-side frame loss), documented in `docs/results_step1.md` |
| Step 2a: laptop -> board over Ethernet, 1-in-5, 60-slot DDR ring, CRC, readback | **PASS** (5 min live camera, 1725/1725 frames, 0 CRC errors, 60/60 slots verified), `docs/results_step2a.md` |
| Web dashboard (camera + what the board holds + events) | Works (`ui/server.py`, port 8765) |
| Face CNN for the FPGA | PARKED (model trained, poor cross-camera generalisation, NOT put on the FPGA) |
| PL detectors: colour = full `image-change-detector` (`hls/image_change.cpp`, replaces `change_rgb`), IR change, audio bands | **PASS: bit-exact on the real board fabric** (116/116, 40/40, 52/52), timing met at 100 MHz, `docs/results_hw_detectors.md` |
| Detector thresholds / trigger rule / fusion | **NOT tuned** (first multi-sensor recording had no usable sound events; see section 7) |
| Firmware that drives the PL detectors, 3-stream relay (colour/IR/mic), trigger, event send | **DONE (Step 2c, 2026-11-21 night)**: `board/sw/src/main.c`; e2e test `tests/step2c_events.py` PASS; live on the real camera. Details in `docs/results_step2c.md` |
| Board -> laptop event window send (TCP :5001, EVT1) | **DONE**: board listens on :5001; the dashboard process (or `gpu/receiver.py`) connects and saves `events/event_NNNN` |
| GPU stage with a vision-language model | **NOT done** (only `gpu/receiver.py` + a basic analyzer exist; no VLM) |

## 3. Hardware and environment facts

**Laptop:** Linux, RTX 3050 Laptop GPU **4096 MiB**, Python venv `.venv` in the repo (torch 2.6+cu124, ultralytics 8.4, opencv 4.13, onnx, matplotlib). Use `.venv/bin/python`.

**Camera (Logitech LVNext, USB 046d:094f):**
- `/dev/video2` main colour camera: YUYV 640x480 (lowest mode, 614,400 B/frame) ~29 fps; MJPEG also available. Raw YUYV loses ~3% of frames camera-side (MJPEG does not).
- `/dev/video4` "Hello" camera: **GREY 480x480, near-infrared face-auth sensor. It is NOT thermal** (no heat signature possible). 26.5 fps alone, ~19 fps when colour + audio capture run concurrently. Dark image (mean ~25) and very noisy (temporal std ~20), so thresholds must be looser than for colour.
- `/dev/video6` CPD (MJPEG 512x640), unused.
- Microphone: ALSA card 2 "LVNext", `arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1`. The room is loud (constant ~60 dB level, mostly < 1 kHz).
- Only **one process can open a camera node**: the dashboard, `relay/relay.py`, recorders and `camera_viewer.py` are mutually exclusive.

**Zedboard (Zynq-7020):** 53,200 LUT, 106,400 FF, 140 BRAM36, 220 DSP, DDR 512 MB. Connections: JTAG (Digilent FT232H, USB `0403:6014`), UART (Cypress CDC, `/dev/ttyACM0`, 115200), Ethernet (1000 Mb/s, PHY Marvell 88E1518 at MDIO address 0). ENET0 MDC/MDIO are on MIO52/53.
- **JTAG firmware/bitstream lives in RAM: a board power cycle wipes it.** After any power cycle, reload (section 8). If `lsusb` shows no `0403:6014`, the PROG/JTAG micro-USB cable is loose (happened once; user reseated it).
- Ethernet: board IP **192.168.7.2**, laptop `enp46s0` **192.168.7.1/24** via a persistent NetworkManager profile `eventcam-board` that the user created (NM's DHCP profile `netplan-enp46s0` used to wipe a manual address). Claude has **no sudo** (no TTY): network changes must be run by the user.
- The board firmware does not recover from an Ethernet link drop; after the laptop link flaps, reload the firmware.

**Xilinx tools (2024.2, `/tools/Xilinx`):** Vivado (use `source /tools/Xilinx/Vivado/2024.2/settings64.sh`), Vitis HLS (`/tools/Xilinx/Vitis_HLS/2024.2/bin/vitis_hls`), `xsdb` (JTAG; auto-launches hw_server on :3121). **The Vitis Python CLI (`vitis -s`) is broken on this install ("Invalid Lopper Installation Directory")**, so firmware is built through HSI via an xsct overlay (section 8). No hls4ml, Vitis AI/DPU or FINN installed. System compiler `arm-none-eabi-gcc` 13.2.

**Network/ports (project protocol, little-endian TCP):** board listens on **:5000** (frames in, `REQ1` readback requests); GPU events were to go **board -> laptop on :5001** (not implemented on the board). The dashboard serves on **:8765** (**8080 is taken by another service on the laptop**).

## 4. Measured results so far

**Step 1** (`tests/step1_camera.py`, `docs/results_step1.md`): MJPEG 640x480: 29.93 fps, p99 interval 40 ms, 0 gaps; raw YUYV: 29.09 fps, 25 gaps > 50 ms (camera-side loss, not exposure/CPU).

**Step 2a** (`tests/step2a_ring.py`, `docs/results_step2a.md`): link ping 0.1 ms; raw TCP laptop->board 29.7 MB/s (238 Mb/s); 5-minute live run: 1725 frames sent = 1725 counted by board, 0 CRC errors, 0 bad lengths, 0 gaps, ring wrapped 28 times, all 60 slots read back with DDR-recomputed CRC = received CRC = relay CRC. 5.75 fps (camera delivers 28.75 fps raw, 1-in-5).

**Hardware detectors** (`docs/results_hw_detectors.md`): see section 5.

## 5. The three PL detectors (the RTL deliverable)

Golden models (integer, bit-exact reference): `sensors/golden.py`.
- **ChangeDetector** (colour and IR): 5x5 box mean (floor) of the Y plane -> 128x96 (colour: Y = even bytes of YUYV 640x480) or 96x96 (IR GREY 480x480); per-pixel background `bg16` (4 fractional bits), `changed = |cur - (bg16>>4)| > pix_thresh`, `bg16 += (cur*16 - bg16) >> bg_shift`. Default `pix_thresh=24`, `bg_shift=3`. Outputs: changed-pixel count, sum of downscaled image (brightness), changed per mille, frame counter. `reset=1` re-initialises the background from the current frame.
- **Goertzel bank** (audio): 512-sample blocks (32 ms at 16 kHz), 24 filters = 8 bands x 3 adjacent 31.25 Hz bins, centres **125, 250, 500, 1000, 2000, 3000, 4000, 6000 Hz**, Q14 integer coefficients (`COEFS` in golden.py, mirrored in `hls/goertzel_coefs.inc`). Outputs 8 signed 64-bit band powers + sum of squares + block counter.

HLS sources (`hls/`): `change_core.h` (shared core), `change_rgb.cpp`, `change_ir.cpp`, `audio_bands.cpp`; testbenches `tb_change.cpp`, `tb_audio.cpp`; vectors from `hls/gen_vectors.py` (synthetic edge cases + real recorded frames/audio with `--session data/sensors/<ts>`); flow script `hls/run_hls.tcl`.

Vivado system: `board/vivado/bd.tcl` (PS7 with Digilent preset + **ENET0 MDIO enabled on MIO52/53**, GP0 -> three IP control ports, three IP data masters -> one AXI interconnect -> PS S_AXI_HP0, FCLK0 100 MHz). Output: `board/vivado_build/eventcam.xsa` (contains `eventcam.bit` and `ps7_init.tcl`). **`bd.tcl` deletes and recreates `board/vivado_build/` on each run.**

Memory-mapped registers (AXI-Lite, 64 KB each):
- Colour `0x40000000`, IR `0x40010000`, Audio `0x40020000`. Each IP's data port can read all DDR `0x00000000-0x1FFFFFFF`.
- Change IPs: `0x00` AP_CTRL (bit0 start, bit1 done [clear on read], bit2 idle), `0x10` frame address (DDR), `0x1c` pix_thresh, `0x24` bg_shift, `0x2c` reset, outputs: `0x34` changed, `0x44` sum_cur, `0x54` score_x1000, `0x64` frames.
- Audio IP: `0x00` AP_CTRL, `0x10` samples address (512 x int16), outputs `0x1c/0x20` sum_sq (lo/hi), `0x40 + 8k` / `0x44 + 8k` band k (lo/hi, signed 64-bit), `0x80` blocks.

Results: C-sim 40/40 colour, 40/40 IR, 52/52 audio, 0 mismatches. Synthesis per kernel: colour 2,963 LUT / 5 DSP / 24 BRAM18, 7.2 ms/frame; IR 3,231 LUT / 5 DSP / 19 BRAM18, 3.1 ms; audio 3,439 LUT / 22 DSP / 3 BRAM18, 0.13 ms/block. Full design: 5,890 LUT (11%), 31 DSP (14%), 24.5 BRAM tiles (17.5%); **timing met at 100 MHz (WNS +0.533 ns, WHS +0.017 ns)**. On the board (`board/sw/hw_test.tcl`, JTAG, ARM core idle): 40/40, 40/40, 52/52 frames/blocks match the golden model exactly.

What this does NOT prove: it was driven over JTAG with the ARM idle (no data cache, no Ethernet). The PL only computes **scores**; the trigger decision (baseline, consecutive-frame rule, fusion) is meant to run in firmware.

## 6. The parked face-detector work (in case it is revisited)

Files: `model/` (`record_faces.py`, `teacher.py`, `build_dataset.py`, `build_public_dataset.py`, `face_net.py`, `train_face.py`, `face_net.pt`, `pretrained/yunet.onnx`). Data under `data/face/` (two recorded sessions of the user, `dataset.npz`, `public.npz`) and `data/public/` (LFW faces, Imagenette, coco128, downloaded).
- Pretrained **YuNet** (OpenCV Zoo, 232 KB ONNX, 53,121 params, 53 convs; ~344 M MACs at its native 640x640) agrees well with a YOLO11n-pose "teacher" on the user's good-angle session. There is no one-click ONNX->RTL path here; the three routes considered were hls4ml on YuNet (untested), a hand-written HLS layer engine (high effort), or distilling into a small net (chosen, then parked).
- `FaceNet` (30,345 params, input 1x96x128 gray, 6x8 logit map, global max) trained on public composites + decoys: on the user's good-angle recording AUC 0.99 (86% recall, 0 false positives on 130 negatives); on the tilted-angle session AUC 0.72 (6% recall) and on a bright room video 0 of 164 faces. Labels are YuNet's, not human. Range limit: faces need to be ~80 px wide in the 640-wide image.
- First user recording session (`20261121_184429`, camera tilted up) has poor labels; second (`20261121_185652`) is good. Faces of the user and bystanders: **keep local, do not upload**.

## 7. Multi-sensor recording and tuning status

`sensors/record_multisensor.py` records colour + IR + mic concurrently with voice-cued phases; `sensors/analyze.py` and `sensors/plot_session.py` analyse it. Session `data/sensors/20261121_192222`.
- Both cameras responded clearly to real movement (colour up to ~300 per mille changed pixels, IR up to ~350) around 3-25 s and 45-60 s, and read ~0 in the still periods. After ~62 s both read zero, including the "both" phase, i.e. **the later phases did not contain the requested movement** (or it happened during the spoken cue, which is excluded).
- **The microphone showed no events at all** (constant ~60 dB, no spikes in "sound only"), so audio thresholds are untuned and the audio detector's usefulness in a loud room is unproven.
- The phase labels are unreliable; do not tune thresholds from this recording. **The user was asked (unanswered at the time of writing): did you clap/move in the later phases, and is the room very loud?**
- Plan: re-record with short, separated bursts (a few distinct claps, a few distinct arm waves, both together), explicit gaps, cues not overlapping the data.

## 8. How to run things (commands)

```bash
# --- sanity checks after a pause or power cycle
lsusb | grep -E "0403:6014|04b4:0008"        # JTAG adapter + UART must both be present
ip -4 -br addr show enp46s0                  # expect 192.168.7.1/24; ping 192.168.7.2
# --- unit tests (keep green after protocol changes)
.venv/bin/python tests/test_all.py           # 7 tests

# --- build + load board firmware (Step 2a ring firmware; current board/sw/src/main.c)
board/sw/build_fw.sh <design.xsa>            # HSI-generated BSP + lwIP + app -> board/fw_build/eventcam.elf
stty -F /dev/ttyACM0 115200 cs8 -cstopb -parenb raw -echo     # then `cat /dev/ttyACM0` to read the log
xsdb board/sw/load.tcl board/fw_build/eventcam.elf <dir>/ps7_init.tcl [<dir>/eventcam.bit]
#   NOTE: the checked-in firmware build used the OLD flagship XSA (flagship/build/zed/zed_top.xsa, ps7_init in flagship/build/zed/xsa_x/).
#   For the PL detectors, unzip board/vivado_build/eventcam.xsa into a FRESH directory (needs ps7_init.tcl + eventcam.bit) and rebuild
#   the firmware against it (build_fw.sh board/vivado_build/eventcam.xsa).
# --- relay / dashboard (they own the camera; run only one)
.venv/bin/python tests/step2a_ring.py --seconds 300 --source camera        # Step 2a test (also runs relay.py)
.venv/bin/python ui/server.py --board 192.168.7.2                          # dashboard on http://127.0.0.1:8765  (--no-board, --synthetic)
# --- hardware detector test on the board (programs the PL; ARM core idle)
xsdb board/sw/hw_test.tcl <unzipped-xsa-dir> $PWD/hls/vectors
# --- HLS flow (run from repo root; projects must be ./hls/proj_<top>, a Vitis HLS relative-path quirk)
export VEC_DIR=$PWD/hls/vectors
HLS_TOP=change_rgb HLS_SRC="change_rgb.cpp" HLS_TB=tb_change.cpp HLS_TBFLAGS="-DSENSOR_RGB" HLS_STEPS="csim syn export" \
  /tools/Xilinx/Vitis_HLS/2024.2/bin/vitis_hls -f hls/run_hls.tcl      # also change_ir (-DSENSOR_IR), audio_bands (tb_audio.cpp, no flags)
# unzip hls/proj_<top>_ip.zip into hls/ip/<top>/ after export, then:
source /tools/Xilinx/Vivado/2024.2/settings64.sh; vivado -mode batch -source board/vivado/bd.tcl   # ~6 min; add -tclargs stop_after_bd to only build the BD
```

Firmware build notes (`board/sw/build_fw.sh`): builds a private copy of the Vivado-bundled xsct (`~/.cache/eventcam/xsct_overlay`, because the root-owned install lacks `scripts/hsm`), generates the lwIP BSP with HSI, patches the generated Makefile (it blanks `COMPILER_FLAGS`) and `xparameters.h` (adds `XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ 650000000`), compiles with Cortex-A9 flags, links with `board/sw/lscript.ld` (program in DDR `0x00100000-0x0FFFFFFF`). No SCU timer driver exists in this install: `src/xscutimer.{c,h}` is a register-level stand-in. `main.c` sets MIO52/53 for MDIO itself (the borrowed flagship XSA did not); the new `eventcam.xsa` also enables it.

## 9. Repo map

- `common/proto.py` wire protocol. `FRM1` header 32 B `<4sIQHHB3xII` (magic, frame_id, ts_us, w, h, fmt, pad, len, crc32); `REQ1` 12 B, `RSP1` 24 B header (+payload; includes CRC recomputed from DDR), `STS1` 32 B stats; `EVT1`/`STA1` (old, still used by the sim/GPU receiver: has `person_x1000`, no crc, not yet updated). `NSLOT=60`. `FMT_YUYV=1` only: GREY/PCM formats not defined yet.
- `board/sw/src/main.c` Step 2a firmware: lwIP TCP :5000 parser for FRM1/REQ1, 60-slot ring at `0x10000000` (60 x 614,400 B), CRC32, D-cache flush, readback, 5 s UART stats. **No PL driving, no trigger, no event send yet.**
- `relay/relay.py` camera/synthetic -> board, `--keep-every 5`, CRC log. `ui/` dashboard. `gpu/receiver.py` + `gpu/analyzers/` (EVT1 receiver, `basic` analyzer; `yolo_verify.py` was planned but not written). `board_sim/` Python stand-in of the board (+ motion `detector.py`, `gate.py`); test scaffolding only. `bench/` earlier gated-vs-continuous GPU benchmark (small YOLO keeps the GPU ~3% busy even continuously: gating saves compute only when quiet time dominates).
- `sensors/` golden models + recorder/analysis. `hls/` kernels. `model/` face work. `tests/`, `docs/` (protocol and results), `data/` (~1 GB, local only; `data/face`, `data/sensors` contain people), `board/ws/` is a leftover empty Vitis workspace (ignore), `README.md` is from earlier and may be stale.

## 10. Gotchas that cost time (avoid repeating)

- **`pkill -f <pattern>` kills your own shell** when the pattern appears in the command line (exit 144). Use `pgrep -x`/PIDs, or a `[x]` bracket trick, in a separate command.
- `rm -rf *` after a `cd` is blocked by the safety check; use fresh empty directories instead of deleting.
- Claude has no sudo and the auto-mode classifier blocked `nmcli`; ask the user to run network/root commands in their own terminal.
- Reloading the board (`rst -system`) bounces the Ethernet link; if the laptop address vanishes, check the NM profile, then reload the firmware.
- Vivado batch prints "Exiting Vivado" for sub-processes; the main script's end marker is `DONE`. HP0 AXI automation fails for HLS masters in this release: `bd.tcl` wires the interconnect by hand. BD "critical warnings" about DDR DQS skew come from the Digilent preset and are normal.
- `xil_printf` does not handle `%lu` (prints garbage): cast to `unsigned` and use `%u`.
- HLS: csim needs the `VEC_DIR` env var; project directories must sit directly under `hls/`.
- The face "faces" labels come from models, not humans; the phase labels of recordings are unreliable until verified against images/plots (look at a contact sheet / plot before trusting any recording).
- Never send camera frames, audio or datasets to an outside service without asking the user (privacy).

## 11. What to do next (in order)

1. **Ask the user** the two pending questions (section 7) and re-record the multi-sensor tuning set with short separated bursts; look at the plot before tuning.
2. **Firmware step (needs the new XSA):** extend the protocol with stream ids/formats (colour YUYV, IR GREY 230,400 B, PCM16 blocks of 512 samples); firmware keeps per-stream rolling caches (proposed memory map, *not implemented*: colour ring `0x10000000`, IR ring ~`0x14000000` (60 x 230,400 B), audio ring ~`0x16000000`); on each arriving unit: `Xil_DCacheFlushRange`, write the IP's address/params, start, poll done, read scores; then the trigger rule in C (colour/IR: warm-up ~25 frames, K consecutive over threshold, cooldown; audio: per-band baseline EMA, ratio threshold with an absolute floor; fusion e.g. any-of / 2-of-3), then send the cached window (extend EVT1) on :5001. Relay: `--keep-every 5` for colour/IR, audio in 512-sample chunks.
3. **Dashboard:** three streams, per-sensor trigger lights and scores, window thumbnails (the page currently says no detector exists: update it).
4. **GPU stage:** a small vision-language model that fits 4 GB (about 2-3B parameters, 4-bit) describing the triggered window; a Nemotron-class VL model (about 8-12B) will not fit. Using hosted Nemotron via NVIDIA's API would send frames off the laptop: **only with the user's explicit OK**.
5. Final write-up: `docs/results_*.md` with measured numbers and an honest works/doesn't-work table. Stretch: move the trigger/baseline logic into the PL.

## 12. Working agreements with this user

Report pass/fail with measured numbers after each step; say plainly when something is unverified; do not claim hardware works until it was run on the board; diagnose rather than explain away a failed check (e.g. the `fid_gaps` false alarm in Step 2a was a firmware bug that was fixed and the 5-minute test rerun clean). The user may be in a loud hall, between tasks, and short on time: keep replies short, lead with the result.

## 13. Step 2c status (added later the same night)

- Firmware `board/sw/src/main.c` (old Step 2a version kept as `board/sw/main_step2a.c.bak`): FRM1 `fmt` selects the stream (1 colour YUYV, 2 IR GREY 480x480, 3 PCM16 x512), each with its own DDR ring (colour `0x10000000` 60 slots, IR `0x18000000` 60 slots, audio `0x1C000000` 600 slots). After CRC + cache flush each frame runs through its PL IP (`image_change` 0x40000000, `change_ir` 0x40010000, `audio_bands` 0x40020000). **Only the colour image-change `fired` onset is a trigger**; IR and audio are measured and shown, not yet fused (untuned).
- Event streaming (replaces the old fixed pre/post window + cooldown): **motion-gated, nothing is sent while static.** On a detector `fired` onset the board sends `pre` (4) pre-roll frames from the ring, then every received colour frame with its timestamp until `hang` (6) frames after motion stops (EVF1 per frame on :5001, EVE1 closes a chunk). Sustained motion is cut into chunks of at most `max_chunk_s` (30 s, by frame timestamps); each chunk is its own event on the laptop (`gpu/chunks.py`, `events/event_NNNN/meta.json`, kind `motion`). No GPU client connected = the episode is dropped and counted.
- **Scene context:** at least `ctx_frames` (10) frames per `ctx_period_s` (60 s, 0 = off) are sent even when static, as a chunk of kind `context` (EVF1 flag bit2, EVE1 reason 3); one baseline burst right after a GPU client connects. Motion frames count towards the 10-frame minimum; context frames do not. The VLM uses the latest context description as "scene before".
- Params are in `common/proto.py` `PARAM_NAMES` (same order as the firmware enum; `ctx_period_s`, `ctx_frames` appended after `reset`). A firmware reload resets them to defaults. After a board reload the dashboard's :5001 socket used to hang on the dead connection; it now uses TCP keepalive and reconnects within ~10 s. A reload sometimes needs a second try (Ethernet autonegotiation).
- GPU stage on the laptop: `gpu/analyzers` (basic, YOLO11n-pose people/posture) plus **`vlm_agent/`**, a self-contained, deletable folder: llama.cpp (CUDA) + Qwen3-VL-2B Q4_K_M, resident and idle until a chunk arrives; 4 s windows, <= 4 frames, 336 px, report JSON/Markdown with timestamps (`scene.json`). Setup: `vlm_agent/setup.sh`; checks: `.venv/bin/python -m vlm_agent.tests.check_agent`. RGB only; thermal/audio not streamed from the board yet. Analysis runs in a worker thread so it never blocks the board stream. Dashboard panel 4 shows nvtop-style GPU stats and the model state.
- New messages on :5000: `REQ1` slot `0xFFFFFFFE` -> `DET1` (356 B: detector registers, 8x8 cell counts, audio bands, params); `CFG1` (24 x u32) sets parameters live (`common/proto.py`: `pack_cfg`, `parse_det`). The dashboard has a detector panel with these and an Apply/Reset-background control.
- Dashboard (`ui/server.py`) now owns colour camera, IR camera (`--ir-device 4`), microphone (`--mic plughw:2,0`) and the :5001 event receiver (runs the analyzer cascade). Run only one of dashboard / relay / recorders.
- Rebuild/reload: `board/sw/build_fw.sh board/vivado_build/eventcam.xsa`; unzip that XSA into a fresh dir; `xsdb board/sw/load.tcl board/fw_build/eventcam.elf <dir>/ps7_init.tcl <dir>/eventcam.bit`. The build script now deletes `libxil.a` before `ar` (stale archive made the first build fail).
- HLS gotcha: a constant offset inside the kernel (`+143488`) wrapped in the generated RTL and shifted reads by 256 KiB on the board while C-sim and RTL co-sim passed; the host now passes the crop address (frame start + 143488). Always run the on-board test (`board/sw/hw_test.tcl`) after a kernel change.
- `pkill -f`/`pgrep -f` with a pattern that also appears in your own command line kills your shell (exit 144): look the PID up in a separate command.

## 14. Audio trigger, audio streaming, model profiles (added 2026-11-22)

- **Trigger union:** firmware param `trig_mode` (0 = video only, 1 = video OR audio). The audio decision is in the PS from the PL `audio_bands` result: block energy (sum of squares) vs a slow baseline (adapts only while quiet), `aud_ratio_x10` (40 = 4x energy), `aud_persist` blocks (32 ms each), `aud_floor_rms`, plus ~1 s hold. An episode stays open while either detector fires. DET1 is now 420 B (40 fields, 32 params; `NPARAM` = 32).
- **Audio goes with the chunk:** new `EVA1` messages on :5001 (16 blocks of 1024 B PCM16 per message, from the audio ring, starting at the chunk's first video frame time); `gpu/chunks.py` writes `events/event_NNNN/audio.wav` (16 kHz mono) and `meta.audio` (null = no audio, which is different from silence), `meta.trigger_cause` (video / audio / video+audio). EVE1 carries the audio block count. The laptop now numbers events itself (the board restarts its numbering at 1 after every firmware reload).
- **Profiles (`vlm_agent/profiles.py`, switch in dashboard panel 4 or `POST /api/vlm {"profile": id}`):** `qwen3vl_rgb` (Qwen3-VL-2B Q4_K_M, RGB only, trig_mode 0; checkpoint in `vlm_agent/checkpoints/qwen3vl_rgb_v1/`) and `lfm3_omni_av` (LFM3-Omni-2B Q4_K_M + mmproj Q8_0, frames at 2 fps + the audio of the same 4 s window in one request, plus a speech pass with the model's ASR prompt behind a speech-likeness gate; trig_mode 1). Switching unloads one llama-server and loads the other (3-5 s here), applies the profile's board params and is remembered in `vlm_agent/profile.json`; after a board reload the dashboard re-applies the active profile's `trig_mode`. License of LFM3-Omni: LFM Open License v1.0 (free below USD 10M annual revenue for commercial use; check before deployment).
- Verified on the board: `tests/step3_audio.py` 4/4 (audio-only trigger, mode 0 ignores audio, video-only with silent audio, both), `tests/step2c_events.py` A-D still pass; `vlm_agent/tests/check_av.py` 11/11, `check_agent.py` 9/9. Peak GPU memory in use with one model + YOLO about 2.5 GB of 4 GB.
- Gotchas: ASR models invent words on non-speech audio (LFM answered "Thank you." on a tone), hence the gate; a live busy-hall microphone with `trig_mode` 1 fires often (tune `aud_ratio_x10`, `aud_floor_rms`, `aud_persist`); never `pkill -f` a pattern that appears in your own command line.
