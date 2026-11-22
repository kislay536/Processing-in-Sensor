# Step 1: camera → laptop CPU, lowest resolution, 30 fps

Camera: LVNext main colour camera, `/dev/video2`, 640×480 (its lowest mode), requested 30 fps. 30 s runs, `tests/step1_camera.py`. Raw numbers in `step1_result_YUYV.json` and `step1_result_MJPG.json`.

| Mode | Mean fps | p50 / p99 / max interval | Gaps > 50 ms | Verdict |
|---|---|---|---|---|
| **MJPEG** 640×480 | **29.93** | 32.1 / 40.0 / 40.1 ms | 0 | **PASS** |
| **YUYV** (raw) 640×480 | 29.09 | 32.1 / 60.0 / 64.1 ms | 25 | **FAIL** (strict criterion: ≥ 29.5 fps, p99 < 50 ms) |

## What went wrong in YUYV, and what it is not
- The camera's own frame timestamps (V4L2 buffer time) show the same gaps, so this is the camera/USB path skipping frames, **not** host read jitter. About 3% of frames are lost, in bursts of two consecutive frames, roughly once a second.
- It is **not** exposure: auto exposure, manual 10 ms and manual 5 ms all drop at the same rate.
- It is **not** CPU load (0.5% of one core) and no read failed; every frame that arrived was exactly 614,400 bytes.
- MJPEG at the same resolution has no gaps. I did not find the root cause (USB scheduling of the larger raw stream is my guess, unverified).

## Decision for the next steps
The downstream pipeline keeps 1 frame in 5 (6 fps), so occasional lost camera frames only make the spacing between kept frames uneven (about 167 ms ± 33 ms); they do not change the rate. I proceed with **raw YUYV** (the board never has to decode JPEG) and treat Step 1 as: **passes in MJPEG, fails the strict 30 fps criterion in raw YUYV with about 3% camera-side loss that does not matter at 6 fps.** If a clean 30 fps raw stream is required, the alternative is MJPEG capture plus a JPEG→YUYV conversion on the laptop, which would put a decode step on the laptop that the dumb-relay design avoids.
