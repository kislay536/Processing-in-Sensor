# Step 2c results: firmware + PL detectors + trigger + event window (2026-11-21)

Measured on the real board with `board/fw_build/eventcam.elf` and the `image_change` bitstream.

| Check | Result |
|---|---|
| Build against the new XSA | OK (after fixing the stale `libxil.a` archive step) |
| `tests/step2c_events.py` (synthetic block appears at 12 s, 40 s run, 241 colour frames) | **PASS**: 1 event, trigger frame 74 (block appears ~frame 72-73; persistence 2), 30 frames, 18.4 MB received, 0 CRC errors |
| Event window content | frames 60..89, block absent in 60..72 and present from 73 (checked on the saved JPEGs) |
| Live real camera + IR + microphone through the dashboard | colour 672 frames, 0 CRC errors, 0 length errors, 0 gaps; IR frames and audio blocks reach their IPs (audio bands non-zero); image IP time per frame 3.07 ms; events produced on real motion (a person moving in view) |
| Live parameter change (`CFG1`) from the dashboard API | round trip verified (min_cells, cooldown read back from the board) |
| `tests/test_all.py` | 7/7 OK |

Not verified: detection quality (false-alarm rate in a quiet room, missed motion) with tuned thresholds; IR and audio are not part of the trigger; no VLM on the GPU stage yet; behaviour after an Ethernet link drop (the firmware still needs a reload).
