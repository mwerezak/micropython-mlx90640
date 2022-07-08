import struct
from array import array
from ucollections import namedtuple
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
    def iter_sp_pix(cls, sp):
        return (
            (row, col)
            for row in range(NUM_ROWS)
            for col in range(NUM_COLS)
            if (row + col) % 2 == sp
        )

    @classmethod
    def iter_sp(cls):
        return (
            (idx//32 - (idx//64)*2) ^ (idx - (idx//2)*2)
            for idx in range(NUM_ROWS * NUM_COLS)
        )

class InterleavedPattern:
    pattern_id = 0x0

    @classmethod
    def iter_sp_pix(cls, sp):
        return (
            (row, col)
            for row in range(sp, NUM_ROWS, 2)
            for col in range(NUM_COLS)
        )

    @classmethod
    def iter_sp(cls):
        return (
            idx//32 - (idx//64)*2
            for idx in range(NUM_ROWS * NUM_COLS)
        )

_READ_PATTERNS = {
    pat.pattern_id : pat for pat in (ChessPattern, InterleavedPattern)
}

def get_pattern_by_id(pattern_id):
    return _READ_PATTERNS.get(pattern_id)


class Subpage:
    def __init__(self, pattern, sp_id):
        self.pattern = pattern
        self.id = sp_id

    def iter_sp_pix(self):
        return self.pattern.iter_sp_pix(self.id)
    def iter_sp(self):
        return self.pattern.iter_sp()


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

_EMISSIVITY = const(1)

class ProcessedImage:
    def __init__(self, calib):
        # pix_data should be a sequence of ints
        self.calib = calib
        self.pix = Array2D.filled('f', NUM_ROWS, NUM_COLS, 0)

    def update(self, pix_data, subpage, state):
        pix_os_cp = self._calc_os_cp(subpage, state)
        for row, col, raw in pix_data:
            ## IR data compensation - offset, Vdd, and Ta
            kta = self.calib.pix_kta.get_coord(row, col)
            kv = self.calib.kv_avg[row % 2][col % 2]
            os_ref = self.calib.pix_os_ref.get_coord(row, col)
            v_os = raw*state.gain - os_ref*(1 + kta*state.ta)*(1 + kv*state.vdd)

            ## IR data gradient compensation
            v_ir = v_os/_EMISSIVITY - self.calib.tgc*pix_os_cp
            self.pix.set_coord(row, col, v_ir)

    def _calc_os_cp(self, subpage, state):
        offset_cp = self.calib.offset_cp[subpage.id]
        if subpage.pattern is InterleavedPattern:
            offset_cp += self.calib.il_chess_c1
        return state.cp[subpage.id] - offset_cp*(1 + self.calib.kta_cp*state.ta)*(1 + self.calib.kv_cp*state.vdd)