from dataclasses import asdict

import numpy as np

from .config import DetectorConfig
from .fixedpoint import (BLOCK_LAYOUT, CELL_SHAPE, EXPOSURE_SHIFT, Q_BITS,
                         Q_MAX, Q_ONE, SHAPE, shift_toward_zero)
from .types import DetectionResult, Reason


class ImageChangeDetector:
    SCHEMA = 1

    def __init__(self, config: DetectorConfig, roi: np.ndarray):
        if not isinstance(config, DetectorConfig):
            raise TypeError("Expected DetectorConfig")
        if not isinstance(roi, np.ndarray) or roi.shape != SHAPE or roi.dtype != np.bool_:
            raise ValueError("Expected a 64 x 64 boolean ROI")
        self.config = config
        self._roi = roi.copy()
        self._n_roi = int(np.count_nonzero(self._roi))
        if self._n_roi == 0:
            raise ValueError("ROI must include at least one pixel")
        counts = np.sum(self._roi.reshape(BLOCK_LAYOUT), axis=(1, 3), dtype=np.uint8)
        self._eligible = counts > 0
        eligible_count = int(np.count_nonzero(self._eligible))
        if config.min_cells > eligible_count:
            raise ValueError("min_cells exceeds the number of eligible ROI cells")
        self._horizontal = np.zeros(CELL_SHAPE, dtype=bool)[:, :-1].copy()
        self._vertical = np.zeros(CELL_SHAPE, dtype=bool)[:-1, :].copy()
        if not self._has_pair(self._eligible):
            raise ValueError("ROI must include two edge-adjacent eligible cells")
        # Python integers preserve the exact ceiling even for large JSON fractions.
        num, den = config.cell_fraction_num, config.cell_fraction_den
        self._required = np.array([(int(n) * num + den - 1) // den for n in counts.flat],
                                  dtype=np.uint8).reshape(CELL_SHAPE)
        self._score = np.array([255 * k // eligible_count for k in range(eligible_count + 1)],
                               dtype=np.uint8)
        self._model = ({"B": np.zeros(SHAPE, np.uint8), "V": np.zeros(SHAPE, np.uint8)}
                       if config.bg_mode == "sigma_delta" else {"Bq": np.zeros(SHAPE, np.uint16)})
        self._background = np.empty(SHAPE, np.int32)
        self._threshold = np.empty(SHAPE, np.int32)
        self._signed = np.empty(SHAPE, np.int32)
        self._residual = np.empty(SHAPE, np.int32)
        self._work = np.empty(SHAPE, np.int32)
        self._candidate = np.empty(SHAPE, np.int32)
        self._changed = np.empty(SHAPE, bool)
        self._counts = np.empty(CELL_SHAPE, np.uint8)
        self._active = np.empty(CELL_SHAPE, bool)
        self.reset()

    def _has_pair(self, mask):
        np.logical_and(mask[:, :-1], mask[:, 1:], out=self._horizontal)
        np.logical_and(mask[:-1, :], mask[1:, :], out=self._vertical)
        return bool(self._horizontal.any() or self._vertical.any())

    def reset(self):
        self._initialized = False
        self._persistence = 0
        self._hold_remaining = 0
        self._update_index = 0
        for array in self._model.values():
            array.fill(0)

    def _initialize(self, frame):
        if "B" in self._model:
            self._model["B"][:] = frame
            self._model["V"].fill(self.config.var_init)
        else:
            np.left_shift(frame, Q_BITS, dtype=np.uint16, out=self._model["Bq"])
        self._initialized = True

    def _suppressed(self, reason, changed=0):
        self._persistence = 0
        return DetectionResult(0, False, False, 0, changed, 0, reason,
                               np.zeros(CELL_SHAPE, np.uint8))

    def _classify(self, residual):
        np.greater(residual, self._threshold, out=self._changed)
        np.logical_and(self._changed, self._roi, out=self._changed)
        return int(np.count_nonzero(self._changed))

    def _exposure(self, frame):
        cfg = self.config
        if not cfg.illumination_enabled:
            return False
        offset = shift_toward_zero(int(self._signed.sum(dtype=np.int64)), EXPOSURE_SHIFT)
        if abs(offset) < cfg.illumination_min_offset:
            return False
        np.add(self._background, offset, out=self._candidate)
        np.clip(self._candidate, 0, 255, out=self._candidate)
        np.subtract(frame, self._candidate, out=self._work)
        np.abs(self._work, out=self._work)
        remaining = self._classify(self._work)
        if remaining * cfg.illumination_residual_den > self._n_roi * cfg.illumination_residual_num:
            return False
        if "B" in self._model:
            self._model["B"][:] = self._candidate
        else:
            bq = self._model["Bq"]
            np.add(bq, offset * Q_ONE, dtype=np.int32, out=self._work)
            np.clip(self._work, 0, Q_MAX, out=self._work)
            bq[:] = self._work
        return True

    def _adapt(self, frame):
        cfg = self.config
        if "B" in self._model:
            b, v = self._model["B"], self._model["V"]
            np.sign(self._signed, out=self._work)
            np.add(b, self._work, out=self._work)
            np.clip(self._work, 0, 255, out=self._work)
            b[:] = self._work
            np.subtract(self._residual, v, out=self._work)
            np.sign(self._work, out=self._work)
            np.add(v, self._work, out=self._work)
            np.clip(self._work, cfg.var_min, cfg.var_max, out=self._work)
            v[:] = self._work
        else:
            bq = self._model["Bq"]
            np.left_shift(frame, Q_BITS, dtype=np.int32, out=self._work)
            np.subtract(self._work, bq, out=self._work)
            np.right_shift(self._work, cfg.ema_shift, out=self._work)
            np.add(self._work, bq, out=self._work)
            np.clip(self._work, 0, Q_MAX, out=self._work)
            bq[:] = self._work

    def update(self, frame: np.ndarray) -> DetectionResult:
        if not isinstance(frame, np.ndarray) or frame.shape != SHAPE or frame.dtype != np.uint8:
            raise ValueError("Expected a 64 x 64 uint8 frame")
        self._update_index += 1
        if not self._initialized:
            self._initialize(frame)
            return self._suppressed(Reason.WARMUP)
        cfg = self.config
        if "B" in self._model:
            self._background[:] = self._model["B"]
            np.left_shift(self._model["V"], cfg.var_shift, dtype=np.int32, out=self._threshold)
            np.maximum(self._threshold, cfg.pix_thresh_min, out=self._threshold)
        else:
            np.right_shift(self._model["Bq"], Q_BITS, out=self._background)
            self._threshold.fill(cfg.ema_pixel_threshold)
        np.subtract(frame, self._background, out=self._signed)
        np.abs(self._signed, out=self._residual)
        changed = self._classify(self._residual)
        if self._hold_remaining:
            self._hold_remaining -= 1
            if self._hold_remaining == 0:
                self._initialize(frame)
                return self._suppressed(Reason.GLOBAL_REBASE, changed)
            return self._suppressed(Reason.GLOBAL_HOLD, changed)
        if changed * cfg.global_fraction_den > self._n_roi * cfg.global_fraction_num:
            if self._exposure(frame):
                return self._suppressed(Reason.EXPOSURE_REBASE, changed)
            self._hold_remaining = cfg.freeze_frames
            return self._suppressed(Reason.GLOBAL_HOLD, changed)

        np.sum(self._changed.reshape(BLOCK_LAYOUT), axis=(1, 3), dtype=np.uint8, out=self._counts)
        np.greater_equal(self._counts, self._required, out=self._active)
        np.logical_and(self._active, self._eligible, out=self._active)
        active = int(np.count_nonzero(self._active))
        passed = active >= cfg.min_cells and self._has_pair(self._active)
        self._persistence = min(self._persistence + 1, cfg.persist_frames) if passed else 0
        fired = self._persistence == cfg.persist_frames
        result = DetectionResult(int(self._score[active]), fired, passed, active, changed,
                                 self._persistence, Reason.CHANGE if fired else Reason.NONE,
                                 self._counts.copy())
        self._adapt(frame)
        return result

    def state_dict(self):
        return {
            "schema": self.SCHEMA, "config": asdict(self.config), "roi": self._roi.copy(),
            "initialized": self._initialized, "persistence": self._persistence,
            "hold_remaining": self._hold_remaining, "update_index": self._update_index,
            **{name: array.copy() for name, array in self._model.items()},
        }

    def load_state_dict(self, state):
        expected = {"schema", "config", "roi", "initialized", "persistence", "hold_remaining",
                    "update_index", *self._model}
        if (not isinstance(state, dict) or state.keys() != expected
                or type(state["schema"]) is not int or state["schema"] != self.SCHEMA):
            raise ValueError("Invalid state schema or fields")
        if DetectorConfig.from_mapping(state["config"]) != self.config or state["config"] != asdict(self.config):
            raise ValueError("Incompatible configuration")
        for name, target in {"roi": self._roi, **self._model}.items():
            array = state[name]
            if not isinstance(array, np.ndarray) or array.dtype != target.dtype or array.shape != target.shape:
                raise ValueError(f"Invalid {name} array")
        if not np.array_equal(state["roi"], self._roi):
            raise ValueError("Incompatible ROI")
        index, initialized = state["update_index"], state["initialized"]
        persistence, hold = state["persistence"], state["hold_remaining"]
        if (type(index) is not int or not 0 <= index
                or type(initialized) is not bool or initialized != (index > 0)
                or type(persistence) is not int or not 0 <= persistence <= self.config.persist_frames
                or type(hold) is not int or not 0 <= hold <= self.config.freeze_frames
                or (hold and persistence) or persistence >= max(1, index) or (hold and index < 2)):
            raise ValueError("Invalid state counters")
        if not initialized and any(state[name].any() for name in self._model):
            raise ValueError("Uninitialized model must be zero")
        if initialized and "V" in self._model:
            if state["V"].min() < self.config.var_min or state["V"].max() > self.config.var_max:
                raise ValueError("Variation outside configured range")
        if "Bq" in self._model and state["Bq"].max() > Q_MAX:
            raise ValueError("EMA background outside Q8.8 pixel range")
        for name, array in self._model.items():
            array[:] = state[name]
        self._initialized, self._persistence = initialized, persistence
        self._hold_remaining, self._update_index = hold, index

    def memory_report(self):
        static = ("_roi", "_eligible", "_required", "_score")
        scratch = ("_horizontal", "_vertical", "_background", "_threshold", "_signed",
                   "_residual", "_work", "_candidate", "_changed", "_counts", "_active")
        return {
            "persistent_arrays": {name: array.nbytes for name, array in self._model.items()},
            "static_arrays": {name: getattr(self, name).nbytes for name in static},
            "scratch_arrays": {name: getattr(self, name).nbytes for name in scratch},
            "logical_scalar_bits": {"initialized": 1, "persistence": 16, "hold_remaining": 16,
                                    "update_index": self._update_index.bit_length(), "n_roi": 13},
        }
