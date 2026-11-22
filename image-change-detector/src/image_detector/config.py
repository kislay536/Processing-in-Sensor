from dataclasses import dataclass, fields
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    bg_mode: str = "sigma_delta"
    pix_thresh_min: int = 20
    var_init: int = 4
    var_min: int = 1
    var_max: int = 127
    var_shift: int = 1
    ema_shift: int = 5
    ema_fraction_bits: int = 8
    ema_pixel_threshold: int = 20
    cell_fraction_num: int = 1
    cell_fraction_den: int = 4
    min_cells: int = 2
    persist_frames: int = 2
    global_fraction_num: int = 3
    global_fraction_den: int = 5
    illumination_enabled: bool = True
    illumination_min_offset: int = 10
    illumination_residual_num: int = 1
    illumination_residual_den: int = 20
    freeze_frames: int = 3

    def __post_init__(self):
        for field in fields(self):
            if type(getattr(self, field.name)) is not field.type:
                raise ValueError(f"{field.name} must be {field.type.__name__}")
        if self.bg_mode not in ("sigma_delta", "ema"):
            raise ValueError("bg_mode must be sigma_delta or ema")
        limits = {
            "pix_thresh_min": (0, 255), "ema_pixel_threshold": (0, 255),
            "var_shift": (0, 7), "ema_shift": (1, 8), "ema_fraction_bits": (8, 8),
            "min_cells": (1, 64), "persist_frames": (1, 65535),
            "freeze_frames": (1, 65535), "illumination_min_offset": (1, 255),
        }
        for name, (low, high) in limits.items():
            if not low <= getattr(self, name) <= high:
                raise ValueError(f"{name} must be in {low}..{high}")
        if not 1 <= self.var_min <= self.var_init <= self.var_max <= 255:
            raise ValueError("Require 1 <= var_min <= var_init <= var_max <= 255")
        if not 0 < self.cell_fraction_num <= self.cell_fraction_den:
            raise ValueError("Cell fraction must be in (0, 1]")
        if not 0 < self.global_fraction_num < self.global_fraction_den:
            raise ValueError("Global fraction must be in (0, 1)")
        if (self.illumination_residual_den <= 0
                or not 0 <= self.illumination_residual_num * self.global_fraction_den
                < self.global_fraction_num * self.illumination_residual_den):
            raise ValueError("Illumination residual fraction must be in [0, global fraction)")

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Configuration must be an object")
        unknown = data.keys() - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
        return cls(**data)

    @classmethod
    def from_json(cls, path):
        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))
