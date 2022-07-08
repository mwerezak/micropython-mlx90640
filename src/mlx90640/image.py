import struct
from array import array
from utils import (
    Struct,
    StructProto,
    field_desc,
    Array2D,
)

from mlx90640.regmap import REG_SIZE
from mlx90640.calibration import NUM_ROWS, NUM_COLS

PIX_STRUCT_FMT = const('>h')
PIX_DATA_ADDRESS = const(0x0400)

class ChessPattern:
    pattern_id = 0x1

    @classmethod
    def get_subpage(cls, sp):
        return (
            (row, col)
            for row in range(NUM_ROWS)
            for col in range(NUM_COLS)
            if (row + col) % 2 == sp
        )

class InterleavedPattern:
    pattern_id = 0x0

    @classmethod
    def get_subpage(cls, sp):
        return (
            (row, col)
            for row in range(sp, NUM_ROWS, 2)
            for col in range(NUM_COLS)
        )

_READ_PATTERNS = {
    pat.pattern_id : pat for pat in (ChessPattern, InterleavedPattern)
}

def get_pattern_by_id(pattern_id):
    return _READ_PATTERNS.get(pattern_id)

## Image Buffers

class RawImage:
    def __init__(self):
        self.pix = Array2D.filled('h', NUM_ROWS, NUM_COLS, 0)

    def read(self, iface, update_idx = None):
        buf = bytearray(REG_SIZE)
        update_idx = update_idx or range(NUM_ROWS * NUM_COLS)
        for row, col in update_idx:
            offset = row * NUM_COLS + col
            iface.read_into(PIX_DATA_ADDRESS + offset, buf)
            self.pix[offset] = struct.unpack(PIX_STRUCT_FMT, buf)[0]

    def iter_subpage(self, iter_idx):
        for row, col in iter_idx:
            yield row, col, self.pix.get_coord(row, col)

class ProcessedImage:
    def __init__(self, calib):
        # pix_data should be a sequence of ints
        self.calib = calib
        self.pix = Array2D.filled('f', NUM_ROWS, NUM_COLS, 0)

    def update(self, pix_data, state):
        for row, col, raw in pix_data:
            kta = self.calib.pix_kta.get_coord(row, col)
            kv = self.calib.kv_avg[row % 2][col % 2]
            os_ref = self.calib.pix_os_ref.get_coord(row, col)
            value = raw*state.gain - os_ref*(1 + kta*state.ta)*(1 + kv*state.vdd)
            self.pix.set_coord(row, col, value)
