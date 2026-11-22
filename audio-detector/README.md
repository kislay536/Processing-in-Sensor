# Audio Detector

A Python API for detecting audio activity in time windows aligned to an integer video frame rate. It uses RMS level in dBFS and supports sound presence and sudden changes.

## Install

Extract the ZIP and run this from the extracted `audio-detector` folder:

```text
python -m pip install .
```

Requires Python 3.11+ and NumPy.

## Analyze an audio file

```python
from pathlib import Path

from audio_detector import AudioConfig, analyze_wav, extract_wav_segment

wav = Path("recording.wav").read_bytes()
config = AudioConfig(fps=30, mode="presence", silence_dbfs=-52, gap_frames=6)
result = analyze_wav(wav, config)

for frame in result["frames"]:
    print(frame["frame"], frame["start_seconds"], frame["active"], frame["reason"])

for segment in result["segments"]:
    excerpt = extract_wav_segment(wav, segment["sample_start"], segment["sample_end"])
    Path("segment-" + str(segment["number"]) + ".wav").write_bytes(excerpt)
```

The file API accepts 16-bit PCM WAV with one or two channels, up to 32 MiB and five minutes. Result frame numbers are one-based. Sample ranges are zero-based and half-open. At 44,100 Hz and 30 frames/s, each full window contains 1,470 samples per channel. For video alignment, match the integer frame rate and the recording start time.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `fps` | 30 | Audio decisions per second |
| `mode` | `"presence"` | Use `"presence"` to retain steady sound, or `"changes"` to flag level changes |
| `silence_dbfs` | -52 | Windows at or below this RMS level are initially inactive |
| `gap_frames` | 6 | Presence mode joins interior quiet gaps of up to this many frames |
| `background_margin_db` | 9 | Changes mode can activate above the rolling background by this amount |
| `onset_db` | 6 | Changes mode can activate after a rise from the previous window by this amount |
| `hold_frames` | 2 | Changes mode may extend activity for this many windows above the silence floor |

## Process a stream

Use one `AudioActivityDetector` per stream and call `update(window)` with successive nonempty NumPy arrays of normalized floating-point PCM samples in `[-1, 1]`. Use the configured window rate. For stereo, pass an array of shape `(samples, channels)`. Call `reset()` before starting a new recording.

The streaming API returns the immediate window decision and RMS diagnostics. The file API adds timestamps, groups active windows, and bridges short quiet gaps in presence mode after observing the next active window. The first window initializes the rolling background in changes mode.

The algorithm averages squared samples and computes `10 * log10(mean_square)`. It makes decisions using total energy over time. Quiet sounds below the silence floor can be missed, and sounds with the same level history produce the same decisions.
