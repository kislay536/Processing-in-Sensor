from dataclasses import dataclass
from enum import IntEnum

import numpy as np


class Reason(IntEnum):
    WARMUP = 0
    NONE = 1
    CHANGE = 2
    EXPOSURE_REBASE = 3
    GLOBAL_HOLD = 4
    GLOBAL_REBASE = 5


@dataclass(frozen=True, slots=True)
class DetectionResult:
    score: int
    fired: bool
    region_pass: bool
    active_cells: int
    changed_pixels: int
    persistence_count: int
    reason: Reason
    cell_counts: np.ndarray

    def to_record(self, include_cells=False):
        record = {
            "score": self.score, "fired": self.fired, "region_pass": self.region_pass,
            "active_cells": self.active_cells, "changed_pixels": self.changed_pixels,
            "persistence_count": self.persistence_count, "reason": self.reason.name,
        }
        if include_cells:
            record["cell_counts"] = self.cell_counts.ravel().tolist()
        return record
