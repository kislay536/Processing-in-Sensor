# Step 2a: laptop → Zedboard over Ethernet, 1 of every 5 frames, 60-slot DDR ring

**Result: PASS** (live camera, 300 s, `tests/step2a_ring.py`; raw numbers in `step2a_result.json`, relay CRC log in `step2a_relay_log.jsonl`).

| Check | Result |
|---|---|
| Frames the board counted vs frames the relay sent | 1725 vs 1725 |
| CRC errors / bad lengths / frame-id gaps | 0 / 0 / 0 |
| Data to the board | 1,059.8 MB (1725 × 614,400 B) at 5.75 fps |
| Ring wrapped (60 slots) | yes, 28 times |
| 60 slots read back from DDR | all match: DDR-recomputed CRC = CRC received = relay's CRC = CRC of the payload received on readback |

Link measurements: ping 0.1 ms, 0% loss; raw TCP laptop → board 29.7 MB/s (238 Mb/s), 8× what 6 fps needs; a 60-frame window (36.9 MB) would take about 1.2 s to send at that rate (not yet measured in the board → laptop direction).

## Notes and caveats
- 5.75 fps rather than 6.00: the camera delivered 8625 raw frames in 300 s (28.75 fps), the known ~3% camera-side loss from Step 1. The relay keeps 1 of every 5 frames it receives, so the rate follows the camera.
- Readback CRC runs over DDR after a cache flush+invalidate, so it checks what is in DDR, not the data cache. It does not yet prove a PL master would see the same bytes (that comes with Step 2c).
- First run of this test showed `fid_gaps=1`: the board's gap check fired when a new relay session restarted at frame 0 (the previous smoke test had left `last_fid=180`). Frame counts and CRCs were already correct. I fixed the firmware to treat frame 0 as a new stream and reran the full 5 minutes from a fresh board; the table above is that rerun.
- The board's firmware does not recover from an Ethernet link drop by itself: after the laptop's link flapped (NetworkManager profile change), the board stopped answering until it was reloaded. Not a problem for the demo as long as the cable stays put; unverified whether it would recover with link-state handling.

## What had to be fixed to get here (all in `board/sw/`)
- Vitis CLI build is broken on this install (Lopper); `build_fw.sh` builds the BSP via HSI and compiles with the system `arm-none-eabi-gcc`.
- The borrowed flagship XSA does not route Ethernet MDC/MDIO (MIO52/53): the PHY was invisible. Firmware sets those pins itself; the Step 2c block design should set them properly.
- No SCU timer driver in the install: a register-level stand-in (`xscutimer.{c,h}`).
- Laptop side: NetworkManager's DHCP profile kept wiping the manual 192.168.7.1; needs the static `eventcam-board` profile.
