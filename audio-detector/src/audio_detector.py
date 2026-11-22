"""Audio activity detection and segment extraction on a video-aligned sample grid."""

from dataclasses import asdict, dataclass
from io import BytesIO
from itertools import groupby
from math import isfinite, log10
import wave

import numpy as np

MAX_WAV_BYTES = 32 * 1024 * 1024
MAX_SECONDS = 300
MIN_DBFS = -100.0


@dataclass(frozen=True, slots=True)
class AudioConfig:
    fps: int = 30
    silence_dbfs: float = -52.0
    background_margin_db: float = 9.0
    onset_db: float = 6.0
    hold_frames: int = 2
    mode: str = "presence"
    gap_frames: int = 6

    def __post_init__(self):
        if self.mode not in ("presence", "changes"):
            raise ValueError("Choose sound presence or sudden changes")
        for name, minimum, maximum in (("fps", 1, 120), ("hold_frames", 0, 120),
                                       ("gap_frames", 0, 120)):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
        for name, minimum, maximum in (
            ("silence_dbfs", -95, 0), ("background_margin_db", 1, 60), ("onset_db", 1, 60),
        ):
            value = getattr(self, name)
            if type(value) not in (int, float) or not minimum <= value <= maximum or not isfinite(value):
                raise ValueError(f"{name} must be a number from {minimum} to {maximum}")

    @classmethod
    def from_mapping(cls, values):
        if not isinstance(values, dict) or values.keys() - cls.__dataclass_fields__.keys():
            raise ValueError("Unknown or malformed audio settings")
        return cls(**values)


class AudioActivityDetector:
    """Process consecutive windows of normalized floating-point PCM."""

    def __init__(self, config: AudioConfig):
        self.config = config
        self.reset()

    def reset(self):
        self.background = None
        self.previous = None
        self.hold = 0

    def update(self, samples):
        power = float(np.mean(np.square(samples, dtype=np.float64)))
        level = max(MIN_DBFS, 10 * log10(power)) if power > 0 else MIN_DBFS
        cfg = self.config
        floor = level if self.background is None else self.background
        rise = 0.0 if self.previous is None else level - self.previous
        above = level - floor
        self.previous = level
        if level <= cfg.silence_dbfs:
            self.hold = 0
            reason = "SILENCE"
        elif cfg.mode == "presence":
            reason = "SOUND"
        elif rise >= cfg.onset_db:
            self.hold = cfg.hold_frames
            reason = "ONSET"
        elif above >= cfg.background_margin_db:
            self.hold = cfg.hold_frames
            reason = "ABOVE_BACKGROUND"
        elif self.hold:
            self.hold -= 1
            reason = "HOLD"
        else:
            reason = "BACKGROUND"

        # The reference falls faster than it rises so a brief loud spike does
        # not raise the floor enough to hide the next event.
        time_constant = 4.0 if above > 0 else 0.6
        self.background = floor + above / (1 + cfg.fps * time_constant)
        return {
            "active": reason in ("SOUND", "ONSET", "ABOVE_BACKGROUND", "HOLD"),
            "reason": reason,
            "rms_dbfs": round(level, 2),
            "background_dbfs": round(floor, 2),
            "rise_db": round(rise, 2),
            "above_background_db": round(above, 2),
        }


def _read_pcm(payload):
    if not 0 < len(payload) <= MAX_WAV_BYTES:
        raise ValueError("Choose a WAV file up to 32 MiB")
    try:
        with wave.open(BytesIO(payload), "rb") as source:
            channels, width, rate, sample_count, _, _ = source.getparams()
            if width != 2 or channels not in (1, 2) or not 1 <= rate <= 192000:
                raise ValueError("Use 16-bit PCM WAV with one or two channels and a supported sample rate")
            if not 0 < sample_count <= rate * MAX_SECONDS:
                raise ValueError("Choose a recording longer than zero and at most five minutes")
            pcm = source.readframes(sample_count)
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Could not read a 16-bit PCM WAV file") from exc
    if len(pcm) != sample_count * channels * width:
        raise ValueError("The WAV audio data is incomplete")
    return pcm, sample_count, channels, rate


def extract_wav_segment(payload: bytes, start: int, end: int) -> bytes:
    """Copy a half-open sample range into a playable PCM WAV."""
    pcm, sample_count, channels, rate = _read_pcm(payload)
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= sample_count:
        raise ValueError("Invalid segment sample range")
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(memoryview(pcm)[start * channels * 2:end * channels * 2])
    return output.getvalue()


def _summarize_segments(frames, max_gap):
    if max_gap:
        start = 0
        for active, run in groupby(frames, key=lambda row: row["active"]):
            rows = list(run)
            end = start + len(rows)
            if not active and start > 0 and end < len(frames) and len(rows) <= max_gap:
                for row in rows:
                    row.update(active=True, reason="BRIDGED_GAP")
            start = end
    segments = []
    for active, run in groupby(frames, key=lambda row: row["active"]):
        if not active:
            continue
        rows = list(run)
        first, last = rows[0], rows[-1]
        number = len(segments) + 1
        first["onset"] = True
        for row in rows:
            row["segment"] = number
        segments.append({
            "number": number, "first_frame": first["frame"], "last_frame": last["frame"],
            "start_seconds": first["start_seconds"], "end_seconds": last["end_seconds"],
            "sample_start": first["sample_start"], "sample_end": last["sample_end"],
        })
    return segments


def analyze_wav(payload: bytes, config: AudioConfig):
    """Decode PCM WAV and group consecutive active frames into segments."""
    pcm, sample_count, channels, rate = _read_pcm(payload)
    if rate < config.fps:
        raise ValueError("The WAV sample rate must be at least the frame rate")
    samples = np.frombuffer(pcm, dtype="<i2").reshape(sample_count, channels)
    detector = AudioActivityDetector(config)
    frames = []
    frame_count = (sample_count * config.fps + rate - 1) // rate
    for index in range(frame_count):
        start = index * rate // config.fps
        end = min(sample_count, (index + 1) * rate // config.fps)
        window = samples[start:end]
        row = detector.update(window.astype(np.float64) / 32768.0)
        row.update(frame=index + 1, start_seconds=index / config.fps,
                   end_seconds=min((index + 1) / config.fps, sample_count / rate),
                   sample_start=start, sample_end=end, onset=False, segment=None,
                   peak_min=round(int(window.min()) / 32768, 4),
                   peak_max=round(int(window.max()) / 32768, 4))
        frames.append(row)
    segments = _summarize_segments(frames, config.gap_frames if config.mode == "presence" else 0)
    return {"config": asdict(config), "sample_rate": rate, "channels": channels,
            "duration": sample_count / rate, "frames": frames, "segments": segments}

