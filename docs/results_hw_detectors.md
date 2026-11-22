# Three PL detectors (colour change, IR change, audio bands): built and verified on the Zedboard

**Result: PASS.** Bit-exact against the golden models (`sensors/golden.py`) in simulation and on the real FPGA fabric.

| Step | Result |
|---|---|
| HLS C-simulation (`hls/`, Vitis HLS 2024.2) | colour 40/40 frames, IR 40/40 frames, audio 52/52 blocks, 0 mismatches (synthetic edge cases + real recorded data) |
| HLS synthesis (xc7z020, 10 ns) | colour 2,963 LUT / 5 DSP / 24 BRAM18, 7.2 ms per frame; IR 3,231 LUT / 5 DSP / 19 BRAM18, 3.1 ms; audio 3,439 LUT / 22 DSP / 3 BRAM18, 0.13 ms per 32 ms block |
| Vivado system (`board/vivado/bd.tcl`) | PS7 + 3 IPs + AXI interconnect to HP0; timing met at 100 MHz (WNS +0.533 ns, WHS +0.017 ns); 5,890 LUT (11%), 7,972 FF (7.5%), 24.5 BRAM tiles (17.5%), 31 DSP (14%) |
| On the board (`board/sw/hw_test.tcl`, JTAG) | colour 40/40, IR 40/40, audio 52/52 match the golden model |

Register map: colour 0x40000000, IR 0x40010000, audio 0x40020000 (64 KB each); each IP reads DDR 0x00000000-0x1FFFFFFF through HP0.

## What this does NOT show yet
- The test drives the IPs over JTAG with the ARM core idle. Running them from firmware (with data caches, frames arriving over Ethernet) is the next step; the firmware must flush the cache before starting an IP (the Step 2a ring code already does).
- It proves the detectors compute the right numbers, not that the thresholds separate real events from quiet: the first multi-sensor recording did not contain usable sound events (see `sensors/analyze.py`, `sensors/plot_session.py`), so audio thresholds are untuned.
- The PL computes per-frame/per-block scores; the trigger rule (baseline, consecutive frames, fusion) will run in firmware.

## Update 2026-11-21 (evening): colour detector replaced by the full image-change detector

`hls/image_change.cpp` (top `image_change`, at `0x40000000`) replaces `change_rgb`. It mirrors `image-change-detector/src/image_detector/detector.py`
(sigma-delta background, 8x8 cell grid, persistence, exposure rebase, global hold/rebase) on a 512x256 centre crop of the 640x480 YUYV frame
(8x4 blocks -> 64x64). `change_ir` and `audio_bands` are unchanged.

- C-sim: 116/116 frames, 0 mismatches (3 synthetic configs incl. exposure and global-hold cases + 30 real frames). Vectors: `hls/gen_vectors.py`.
- Synthesis: ~6.1k LUT, 0 DSP, 12 BRAM18 for the kernel; ~3.0 ms/frame. Full design 6,884 LUT (12.9%), 18.5 BRAM tiles, timing met at 100 MHz.
- On the board (JTAG, ARM idle, `board/sw/hw_test.tcl`): image 116/116, IR 40/40, audio 52/52 match the golden models.
- Register map: 0x10 frame address = address of the crop's first pixel (frame start + 143488); params 0x1c..0x84; outputs fired 0x8c, reason 0x9c, score 0xac,
  region_pass 0xbc, active 0xcc, changed 0xdc, persistence 0xec, cell counts 0x100..0x13f (4 per word), frames 0x140.
- Bug found and fixed on the board: a +143488 offset inside the kernel wrapped in the generated RTL and shifted the read window by 256 KiB; C-sim and a
  4-frame RTL co-sim both missed it (only 3 of 116 board frames matched at first). Fix: the host passes the crop address.
- Not tested: ARM firmware driving this IP, Ethernet traffic, thresholds on real events.
