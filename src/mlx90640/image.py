import struct
from bitutils import (
    Struct,
    StructProto,
    field_desc,
    Array2D,
)

from mlx90640.calibration import NUM_ROWS, NUM_COLS

PIX_DATA_ADDRESS = const(0x0400)
PIX_STRUCT_FMT = const('>h')
PIX_SIZE = struct.calcsize(PIX_STRUCT_FMT)


class ImageData:
    def __init__(self, iface, calib, gain, delta_ta, delta_vdd):
        self.calib = calib
        self.gain = gain
        self.delta_ta = delta_ta
        self.delta_vdd = delta_vdd

        pix_data = self._read_raw_pix(iface)
        pix_data = self._calc_pix_offsets(pix_data)
        self._pix = Array2D('f', NUM_COLS, pix_data)

    @staticmethod
    def _read_raw_pix(iface):
        buf = bytearray(PIX_SIZE)
        for offset in range(NUM_ROWS * NUM_COLS):
            iface.read_into(PIX_DATA_ADDRESS + offset, buf)
            yield from struct.unpack(PIX_STRUCT_FMT, buf)

    def _calc_pix_offsets(self, raw_pix):
        for value, idx in zip(raw_pix, Array2D.index_range(NUM_ROWS, NUM_COLS)):
            row, col = idx
            kta = self.calib.pix_kta[row, col]
            kv = self.calib.kv_avg[row % 2][col % 2]
            os_ref = self.calib.pix_os_ref[row, col]
            yield value*self.gain - os_ref*(1 + kta*self.delta_ta)*(1 + kv*self.delta_vdd)
