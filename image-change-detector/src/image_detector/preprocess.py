import numpy as np

from .fixedpoint import GRAY_SHIFT, RGB_WEIGHTS, SIZE


class Preprocessor:
    def __init__(self, height, width, channels="gray"):
        if channels not in ("gray", "rgb"):
            raise ValueError("Expected gray or rgb channel format")
        if any(type(n) is not int or n < SIZE or n % SIZE for n in (height, width)):
            raise ValueError("Height and width must be positive multiples of 64")
        self.bh, self.bw = height // SIZE, width // SIZE
        if any(block & (block - 1) for block in (self.bh, self.bw)):
            raise ValueError("Each block dimension must be a power of two")
        area = self.bh * self.bw
        if area * 255 > np.iinfo(np.uint32).max:
            raise ValueError("Block sum would overflow uint32")
        self.shift = area.bit_length() - 1
        self.shape = (height, width, 3) if channels == "rgb" else (height, width)
        self.channels = channels

    def __call__(self, frame):
        if not isinstance(frame, np.ndarray) or frame.shape != self.shape or frame.dtype != np.uint8:
            raise ValueError(f"Expected uint8 array of shape {self.shape}")
        gray = frame
        if self.channels == "rgb":
            rgb = frame.astype(np.uint16)
            gray = sum((rgb[..., i] * weight for i, weight in enumerate(RGB_WEIGHTS))) >> GRAY_SHIFT
        blocks = gray.reshape(SIZE, self.bh, SIZE, self.bw)
        return (blocks.sum(axis=(1, 3), dtype=np.uint32) >> self.shift).astype(np.uint8)
