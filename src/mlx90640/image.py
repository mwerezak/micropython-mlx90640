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
    def iter_sp_pix(cls, sp_id):
        return (
            (row, col)
            for row in range(NUM_ROWS)
            for col in range(NUM_COLS)
            if (row + col) % 2 == sp_id
        )

    @classmethod
    def iter_sp(cls):
        return (
            cls.get_sp(idx) for idx in range(NUM_ROWS * NUM_COLS)
        )

    @classmethod
    def get_sp(cls, idx):
        return (idx//32 - (idx//64)*2) ^ (idx - (idx//2)*2)

class InterleavedPattern:
    pattern_id = 0x0

    @classmethod
    def iter_sp_pix(cls, sp_id):
        # return (idx for idx, sp in enumerate(cls.iter_sp()) if sp == sp_id)
        return (
            (row, col)
            for row in range(sp, NUM_ROWS, 2)
            for col in range(NUM_COLS)
        )

    @classmethod
    def iter_sp(cls):
        return (
            cls.get_sp(idx) for idx in range(NUM_ROWS * NUM_COLS)
        )

    @classmethod
    def get_sp(cls, idx):
        return idx//32 - (idx//64)*2

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
        if self.calib.use_tgc:
            pix_os_cp = self._calc_os_cp(subpage, state)
            pix_alpha_cp = self.calib.pix_alpha_cp[subpage.id]

        for row, col, raw in pix_data:
            ## IR data compensation - offset, Vdd, and Ta
            kta = self.calib.pix_kta.get_coord(row, col)
            kv = self.calib.kv_avg[row % 2][col % 2]
            
            offset = self.calib.pix_os_ref.get_coord(row, col)
            offset *= (1 + kta*state.ta)*(1 + kv*state.vdd)

            v_os = raw*state.gain - offset

            if subpage.pattern is InterleavedPattern:
                v_os += self.calib.il_offset.get_coord(row, col)
            v_ir = v_os / _EMISSIVITY

            ## IR data gradient compensation
            if self.calib.use_tgc:
                v_ir -= self.calib.tgc*pix_os_cp

            ## sensitivity normalization
            alpha = self.calib.pix_alpha.get_coord(row, col)
            if self.calib.use_tgc:
                alpha -= self.calib.tgc*pix_alpha_cp
            alpha *= (1 + self.calib.ksta*state.ta)
            v_ir /= alpha

            self.pix.set_coord(row, col, v_ir)


    def _calc_os_cp(self, subpage, state):
        pix_os_cp = self.calib.pix_os_cp[subpage.id]
        if subpage.pattern is InterleavedPattern:
            pix_os_cp += self.calib.il_chess_c1
        return state.gain_cp[subpage.id] - pix_os_cp*(1 + self.calib.kta_cp*state.ta)*(1 + self.calib.kv_cp*state.vdd)

    def _calc_os_cp2(self, pattern, state):
        pix_os_cp = list(self.calib.pix_os_cp)
        if pattern is InterleavedPattern:
            for i in range(len(pix_os_cp)):
                pix_os_cp[i] += self.calib.il_chess_c1

        k = (1 + self.calib.kta_cp*state.ta)*(1 + self.calib.kv_cp*state.vdd)
        return [
            gain_cp_sp - pix_os_cp_sp*k
            for pix_os_cp_sp, gain_cp_sp in zip(pix_os_cp, state.gain_cp)
        ]
