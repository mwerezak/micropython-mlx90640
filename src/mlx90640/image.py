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

class RawImage:
    def __init__(self):
        self.pix = Array2D.filled('h', NUM_ROWS, NUM_COLS, 0)

    def read(self, iface):
        buf = bytearray(REG_SIZE)
        for offset in range(NUM_ROWS * NUM_COLS):
            iface.read_into(PIX_DATA_ADDRESS + offset, buf)
            self.pix[offset] = struct.unpack(PIX_STRUCT_FMT, buf)[0]


class ProcessedImage:
    def __init__(self, pix_data, calib, state):
        # pix_data should be a sequence of ints
        self.calib = calib
        self.state = state

        self.pix = Array2D.from_iter('f', NUM_COLS, self._calc_pix_offsets(pix_data))

    @property
    def pixbuf(self):
        return self.pix.array

    def _calc_pix_offsets(self, raw_pix):
        for value, idx in zip(raw_pix, Array2D.range(NUM_ROWS, NUM_COLS)):
            row, col = idx
            kta = self.calib.pix_kta.get_coord(row, col)
            kv = self.calib.kv_avg[row % 2][col % 2]
            os_ref = self.calib.pix_os_ref.get_coord(row, col)
            yield value*self.state.gain - os_ref*(1 + kta*self.state.ta)*(1 + kv*self.state.vdd)
