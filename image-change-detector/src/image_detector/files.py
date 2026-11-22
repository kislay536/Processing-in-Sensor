from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .config import DetectorConfig
from .detector import ImageChangeDetector
from .fixedpoint import SHAPE, SIZE
from .preprocess import Preprocessor
from .types import DetectionResult


@dataclass(frozen=True, slots=True)
class FileDetection:
    path: Path
    source_frame: int
    time_seconds: float | None
    result: DetectionResult


def _crop_box(width: int, height: int) -> tuple[int, int, int, int]:
    if min(width, height) < SIZE:
        raise ValueError(f"Images must be at least {SIZE} × {SIZE} pixels")

    def compatible_size(length: int) -> int:
        return SIZE << ((length // SIZE).bit_length() - 1)

    crop_width, crop_height = compatible_size(width), compatible_size(height)
    left, top = (width - crop_width) // 2, (height - crop_height) // 2
    return left, top, left + crop_width, top + crop_height


def evaluate_files(
    paths: Iterable[str | Path],
    *,
    config: DetectorConfig | None = None,
    roi: np.ndarray | None = None,
    stride: int = 1,
    source_fps: float | None = None,
    center_crop: bool = False,
) -> Iterator[FileDetection]:
    """Yield detections in input order, starting at source frame 1."""
    if type(stride) is not int or stride < 1:
        raise ValueError("stride must be a positive integer")
    if source_fps is not None and (
        isinstance(source_fps, bool) or not isfinite(source_fps) or source_fps <= 0
    ):
        raise ValueError("source_fps must be a positive finite number")
    detector = ImageChangeDetector(
        config if config is not None else DetectorConfig(),
        roi if roi is not None else np.ones(SHAPE, dtype=bool),
    )
    geometry = None
    preprocessor = None
    crop = None
    for index, entry in enumerate(paths):
        if index % stride:
            continue
        path = Path(entry)
        try:
            with Image.open(path) as decoded:
                source = ImageOps.exif_transpose(decoded)
                if geometry is None:
                    geometry = source.size
                    width, height = geometry
                    if center_crop:
                        crop = _crop_box(width, height)
                        width, height = crop[2] - crop[0], crop[3] - crop[1]
                    preprocessor = Preprocessor(height, width, "rgb")
                elif source.size != geometry:
                    raise ValueError(f"Expected dimensions {geometry}, got {source.size}")
                if crop is not None:
                    source = source.crop(crop)
                if "A" in source.getbands() or "transparency" in source.info:
                    rgba = source.convert("RGBA")
                    base = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
                    source = Image.alpha_composite(base, rgba)
                rgb = np.asarray(source.convert("RGB"))
                reduced = preprocessor(rgb)
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path}: {exc}") from exc

        yield FileDetection(
            path=path,
            source_frame=index + 1,
            time_seconds=index / source_fps if source_fps is not None else None,
            result=detector.update(reduced),
        )
