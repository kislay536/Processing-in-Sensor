"""Energy / bandwidth analysis: FPGA-gated pipeline (measured) versus "send everything to the GPU" (analytical model calibrated by an
isolated GPU measurement). Self-contained: delete this folder and the dashboard still works (all hooks are guarded)."""
from .model import METER, calibrate, load_calibration, load_assumptions, save_assumptions, summary_json, start

__all__ = ["METER", "calibrate", "load_calibration", "load_assumptions", "save_assumptions", "summary_json", "start"]
