# PiSe protocol

TCP, little-endian, fixed binary headers (easy in C/lwIP). The board is the server.

| Port | Direction | Messages |
|---|---|---|
| 5000 | relay → board | `FRM1` |
| 5001 | board → GPU stage | `EVT1`, `STA1` |

`FRM1` (28-byte header + payload): `magic[4]="FRM1", frame_id u32, ts_us u64, w u16, h u16, fmt u8 (1=YUYV), pad[3], len u32`.

`EVT1` (24-byte header, then n_frames records): `magic[4]="EVT1", event_id u32, trigger_frame_id u32, motion_x1000 u16, person_x1000 u16, n_frames u16, w u16, h u16, fmt u8, pad u8`. Each record: `frame_id u32, ts_us u64, len u32, payload`.

`STA1` (32 bytes): `magic[4]="STA1", frames_in u32, triggers u32, bytes_in u64, bytes_out u64, motion_x1000 u16, person_x1000 u16`. Sent about once a second.

Reference implementation: `common/proto.py`. The C header `board/sw/proto.h` will mirror it.
