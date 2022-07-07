import struct
from mlx90640.regmap import (
    Struct,
    StructProto,
    field_desc,
)
from mlx90640.calibration import (
    Array2D,
    NUM_ROWS,
    NUM_COLS,
)

PIX_DATA_ADDRESS = const(0x0400)
PIX_STRUCT_FMT = const('>h')
PIX_SIZE = struct.calcsize(PIX_STRUCT_FMT)


class ImageData:
    def __init__(self, camera):
        self.camera = camera
        self._raw_pix = Array2D('h', NUM_COLS, self._read_raw_pix(camera.iface))

    @staticmethod
    def _read_raw_pix(iface):
        buf = bytearray(PIX_SIZE)
        for offset in range(NUM_ROWS * NUM_COLS):
            iface.read_into(PIX_DATA_ADDRESS + offset, buf)
            yield from struct.unpack(PIX_STRUCT_FMT, buf)

    def _calc_pix_os(self):
        # index by [row % 2][col % 2]
        kta_avg = (
            (eeprom['kta_avg_re_ce'], eeprom['kta_avg_re_co']),
            (eeprom['kta_avg_ro_ce'], eeprom['kta_avg_ro_co']),
        )

        kta_scale_1 = 1 << (eeprom['kta_scale_1'] + 8)
        kta_scale_2 = 1 << eeprom['kta_scale_2']
        print('kta_scale_1:', kta_scale_1)
        print('kta_scale_2:', kta_scale_2)

        for row, col in Array2D.iter_indices(NUM_ROWS, NUM_COLS):
            kta_ee = self.pix_data[row, col]['kta']
            kta_rc = kta_avg[row % 2][col % 2]
            yield (kta_rc + kta_ee * kta_scale_2)/kta_scale_1
