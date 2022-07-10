import struct
from array import array
from ucollections import namedtuple
from utils import (
    Struct,
    StructProto,
    field_desc,
    array_filled,
)

from mlx90640.regmap import REG_SIZE
from mlx90640.calibration import NUM_ROWS, NUM_COLS, TEMP_K

PIX_STRUCT_FMT = const('>h')
PIX_DATA_ADDRESS = const(0x0400)

class _BasePattern:
    @classmethod
    def sp_range(cls, sp_id):
        return (
            idx for idx, sp in enumerate(cls.iter_sp()) 
            if sp == sp_id
        )

    @classmethod
    def iter_sp(cls):
        return (
            cls.get_sp(idx) for idx in range(NUM_ROWS * NUM_COLS)
        )

class ChessPattern(_BasePattern):
    pattern_id = 0x1

    @classmethod
    def get_sp(cls, idx):
        return (idx//32 - (idx//64)*2) ^ (idx - (idx//2)*2)

class InterleavedPattern(_BasePattern):
    pattern_id = 0x0

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

    def sp_range(self):
        return self.pattern.sp_range(self.id)


## Image Buffers

class RawImage:
    def __init__(self):
        self.pix = array_filled('h', NUM_ROWS*NUM_COLS)

    def __getitem__(self, idx):
        return self.pix[idx]

    def read(self, iface, update_idx = None):
        buf = bytearray(REG_SIZE)
        update_idx = update_idx or range(NUM_ROWS * NUM_COLS)
        for offset in update_idx:
            iface.read_into(PIX_DATA_ADDRESS + offset, buf)
            self.pix[offset] = struct.unpack(PIX_STRUCT_FMT, buf)[0]

class ProcessedImage:
    def __init__(self, calib):
        # pix_data should be a sequence of ints
        self.calib = calib
        self.v_ir = array_filled('f', NUM_ROWS*NUM_COLS, 0.0)
        self.alpha = array_filled('f', NUM_ROWS*NUM_COLS, 1.0)

    def update(self, pix_data, subpage, state):
        if self.calib.use_tgc:
            pix_os_cp = self._calc_os_cp(subpage, state)
            pix_alpha_cp = self.calib.pix_alpha_cp[subpage.id]

        for idx, raw in pix_data:
            ## IR data compensation - offset, Vdd, and Ta
            kta = self.calib.pix_kta[idx]

            row, col = divmod(idx, NUM_COLS)
            kv = self.calib.kv_avg[row % 2][col % 2]
            
            offset = self.calib.pix_os_ref[idx]
            offset *= (1 + kta*state.ta)*(1 + kv*state.vdd)

            v_os = raw*state.gain - offset
            if subpage.pattern is InterleavedPattern:
                v_os += self.calib.il_offset[idx]
            v_ir = v_os / self.calib.emissivity

            ## IR data gradient compensation
            if self.calib.use_tgc:
                v_ir -= self.calib.tgc*pix_os_cp
            self.v_ir[idx] = v_ir

            ## sensitivity normalization
            alpha = self.calib.pix_alpha[idx]
            if self.calib.use_tgc:
                alpha -= self.calib.tgc*pix_alpha_cp
            alpha *= (1 + self.calib.ksta*state.ta)
            self.alpha[idx] = alpha

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

    def calc_temperature(self, idx, state):
        v_ir = self.v_ir[idx]
        alpha = self.alpha[idx]

        s_x = v_ir*(alpha**3) + state.ta_r*(alpha**4)
        s_x = (s_x**0.25)*self.calib.ksto[1]

        to = v_ir/(alpha*(1 - TEMP_K*self.calib.ksto[1]) + s_x) + state.ta_r
        to = (to**0.25) - TEMP_K
        return to + self.calib.drift

    def calc_temperature_ext(self, idx, state, to):
        v_ir = self.v_ir[idx]
        alpha = self.alpha[idx]

        band = self._get_range_band(to)
        alpha_ext = self.calib.alpha_ext[band]
        ksto_ext = self.calib.ksto[band]
        ct = self.calib.ct[band]
        to_ext = v_ir/(alpha*alpha_ext*(1 + ksto_ext*(to - ct))) + state.ta_r
        to_ext = (to_ext**0.25) - TEMP_K
        return to_ext  + self.calib.drift

    def _get_range_band(self, t):
        return sum(1 for ct in self.calib.ct if t >= ct) - 1

class TemperatureOutOfRangeError(Exception): pass
