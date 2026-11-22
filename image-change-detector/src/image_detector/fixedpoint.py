SIZE = 64
CELL = 8
GRID = SIZE // CELL
SHAPE = (SIZE, SIZE)
CELL_SHAPE = (GRID, GRID)
BLOCK_LAYOUT = (GRID, CELL, GRID, CELL)
RGB_WEIGHTS = (77, 150, 29)
GRAY_SHIFT = 8
EXPOSURE_SHIFT = 12
Q_BITS = 8
Q_ONE = 1 << Q_BITS
Q_MAX = 255 * Q_ONE


def shift_toward_zero(value, shift):
    return value >> shift if value >= 0 else -((-value) >> shift)


def arithmetic_shift(value, shift):
    return value >> shift
