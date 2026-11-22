# PiSe

**Processing in Sensor towards multimodal inference and applications**

## Motivation

Picture a factory, a warehouse or a wildlife-health monitoring site run by AI, with hundreds of cameras and sensors spread over many places. Three problems appear as soon as every sensor streams everything to a central server:

1. **Storage.** All camera and sensor output has to be stored continuously, although the important events are short and in most frames nothing changes at all. Most of the storage holds nothing of interest.
2. **Compute and power.** If this stream is fed to an AI system, the server processes every frame and sequence, including the ones with no activity in them, and burns compute and power that could serve something important. This calls for lightweight filtering that triggers on an important event, so that only that event is processed and not the whole sequence.
3. **Bandwidth.** With N sensors sending to one central server of bandwidth B, each sensor effectively gets B/N. Given that cameras generate new data at a high rate, a high number of N sensors would saturate the bandwidth, making large scale deployments impractical. 

PiSe addresses all three. It places a lightweight custom silicon block right next to the sensor. The block does the essential preprocessing and filtering, finds the events of interest, and sends sensor data only when it is actually needed. This removes the bandwidth bottleneck, saves energy because the GPU no longer spends its compute on empty footage, and lets one server serve many more sensors.

## How it works

PiSe moves computation to where the data is born: the sensor is integrated with custom silicon that filters at the source, so only the moments that matter ever leave it.

**Topology of the prototype**
```
RGB camera (30 fps) + microphone
        │  raw frames and audio
        ▼
laptop: thin relay, no analysis
        │  
        ▼
sensor-side silicon (prototype: FPGA, Zedboard Zynq-7020)
        · image-change detector (video)   · Goertzel filter bank (audio)
        · rolling buffer + trigger (video OR audio)
        │  only when an event is detected: the frames and audio of the event
        ▼
laptop GPU (RTX 3050, 4 GB): small multimodal model (LFM3-Omni-2B, 4-bit)
        │
        ▼
one-sentence description of the event, or any application built on it
```
The silicon cannot be placed inside the camera, so a thin laptop relay forwards the USB camera and microphone to the board. The relay does no analysis.

**What runs where**
- **Video algorithm: image-change detector.** A sigma-delta background model on a 512x256 centre crop of the colour frame, block-averaged to 64x64 and judged on an 8x8 cell grid, with persistence and rejection of exposure or global changes. A hardware block (HLS) on the FPGA.
- **Audio algorithm: Goertzel filter bank.** 24 integer filters (8 bands from 125 Hz to 6 kHz, 3 adjacent 31.25 Hz bins each) on 32 ms blocks at 16 kHz. The audio trigger fires when the sound level rises above its running baseline.
- **Trigger and chunks.** The trigger is the union of video and audio. On an event the board releases a few pre-roll frames from its ring buffer and then the frames and audio of the event, in chunks of at most 2 s. While the scene is static almost nothing is sent, only a short context burst (every 60 s by default, adjustable).
- **Small multimodal model.** LFM3-Omni-2B (RGB and audio, 4-bit) runs through a local `llama.cpp` server on the laptop GPU and answers with one sentence per chunk. In our runs the text appeared a median of 1.0 s after the chunk (p95 1.8 s, 33 chunks).

**Evaluation approach.** The FPGA stands in for the custom silicon, and we judge it the way silicon would be judged:
- **Size:** gate-level synthesis of the video and audio detectors gives about 0.54 million transistors of logic and registers (about 134k gate equivalents), plus about 225 kbit of on-chip memory. A consumer CPU has billions of transistors.
- **Power:** the Vivado estimate for the entire chip, processor system included, is 1.8 W. The energy comparison budgets 3.3 W for the whole board.
- **System:** the dashboard measures GPU power, utilisation, link traffic and energy, and compares them with a GPU-only baseline that analyses everything (10 back-to-back model calls, averaged element by element into one call profile: about 1.05 s per call and 31 W on average on our laptop).

## Setup
```
scripts/setup.sh            # checks tools, creates .venv, installs requirements.txt (add --test to run the unit tests)
scripts/download.sh         # yolo11n-pose.pt + builds llama.cpp (CUDA) + downloads the VLM models (~3 GB)
scripts/download.sh datasets  # optional: public datasets (LFW, Imagenette, COCO128) to rebuild the face model
```
Not in git (see `.gitignore`): `.venv`, model weights, `vlm_agent/third_party`, recorded data and events (camera frames, audio, faces), generated HLS / Vivado build output. The prebuilt bitstream (`board/vivado_build/eventcam.bit`) and firmware (`board/fw_build/eventcam.elf`) are included. Rebuilding the FPGA design needs Vivado / Vitis HLS 2024.2; see `CONTEXT.md`. File and project names that still say `eventcam` are build identifiers from the earlier project name.

## Run
```
.venv/bin/python ui/server.py --board 192.168.7.2      # dashboard on http://127.0.0.1:8765  (--no-board, --synthetic for no hardware)
```
The page at `/` is the full dashboard; `/v2` is the presentation view (timeline, camera, motion and audio panels, model output, energy comparison). Software-only tests: `.venv/bin/python tests/test_all.py`.

## Repository layout
| Folder | Contents |
|---|---|
| `ui/` | Dashboard server and pages (`index.html`, `index_v2.html`) |
| `gpu/` | Chunk receiver and analysis pipeline |
| `vlm_agent/` | Local multimodal model runtime: llama.cpp server, prompts, model profiles |
| `energy/` | GPU power / traffic / energy model, baseline calibration, hardware size estimate |
| `board/`, `hls/` | Sensor-side silicon: Vivado block design, firmware, HLS detectors and exported IP |
| `board_sim/` | Software stand-in and golden model for the sensor-side silicon |
| `relay/`, `common/` | Camera / microphone relay and the wire protocol (`docs/protocol.md`) |
| `sensors/`, `bench/`, `model/`, `tests/`, `docs/` | Recording and analysis tools, benchmarks, small experiments, tests, measured results |

More detail and measurements: `CONTEXT.md`, `docs/`, `energy/hardware_size.md`.
