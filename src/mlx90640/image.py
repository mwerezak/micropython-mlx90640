import struct
from array import array
from mlx90640.regmap import (
    Struct, 
    StructProto,
    field_desc,
    REG_SIZE,
    REG_RAW_FMT,
    twos_complement,
)

OCC_ROWS_ADDRESS = const(0x2412)
OCC_COLS_ADDRESS = const(0x2418)

ACC_ROWS_ADDRESS = const(0x2422)
ACC_COLS_ADDRESS = const(0x2428)

NUM_ROWS = const(24)
NUM_COLS = const(32)
NUM_PIX = const(32 * 24)  # const(NUM_COLS * NUM_ROWS)

PIX_CALIB_PROTO = StructProto((
    field_desc('offset',  6, 10, signed=True),
    field_desc('alpha',   6,  4),
    field_desc('kta',     3,  1, signed=True),
    field_desc('outlier', 1,  0),
))

PIX_CALIB_ADDRESS = const(0x2440)


class Array2D:
    def __init__(self, typecode, stride, init):
        self.stride = stride
        self._array = array(typecode, init)
    def __getitem__(self, idx):
        i, j = idx
        return self._array[i * self.stride + j]
    def __setitem__(self, idx, value):
        i, j = idx
        self._array[i * self.stride + j] = value

class PixelCalibrationData:
    def __init__(self, eeprom):
        self._data = bytearray(NUM_PIX * REG_SIZE)
        for idx in range(NUM_PIX):
            offset = idx * REG_SIZE
            self._data[offset:offset+REG_SIZE] = eeprom.iface.read(PIX_CALIB_ADDRESS + offset)

    def __getitem__(self, pixel):
        # type: (row, col) -> Struct
        row, col = pixel
        idx = row * NUM_COLS + col
        offset = idx * REG_SIZE
        return Struct(self._data[offset:offset+REG_SIZE], PIX_CALIB_PROTO)

class CameraCalibration:
    def __init__(self, eeprom):
        # restore VDD sensor parameters
        self.k_vdd = eeprom['k_vdd'] * 32
        self.vdd_25 = (eeprom['vdd_25'] - 256) * 32 - 8192

        # resolution control
        self.res_ee = eeprom['res_ctrl_cal']

        # ambient temperature
        self.kv_ptat = eeprom['kv_ptat'] / 4096.0
        self.kt_ptat = eeprom['kt_ptat'] / 8.0
        self.ptat_25 = eeprom['ptat_25']
        self.alpha_ptat = eeprom['k_ptat'] / 4.0 + 8

        # gain
        self.gain = eeprom['gain']

        # pixel calibration data
        self.pix_data = PixelCalibrationData(eeprom)
        self.pix_os_ref = Array2D('h', NUM_COLS, self._calc_pix_os_ref(eeprom))

    def _calc_pix_os_ref(self, eeprom):
        offset_avg = eeprom['pix_os_average']
        occ_scale_row = (1 << eeprom['scale_occ_row'])
        occ_scale_col = (1 << eeprom['scale_occ_col'])
        occ_scale_rem = (1 << eeprom['scale_occ_rem'])

        occ_rows = tuple(self._read_cc_iter(eeprom.iface, OCC_ROWS_ADDRESS, NUM_ROWS))
        occ_cols = tuple(self._read_cc_iter(eeprom.iface, OCC_COLS_ADDRESS, NUM_COLS))

        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                yield (
                    offset_avg
                    + occ_rows[row] * occ_scale_row
                    + occ_cols[col] * occ_scale_col
                    + self.pix_data[row, col]['offset'] * occ_scale_rem
                )

    @staticmethod
    def _read_cc_iter(iface, base, size):
        buf = bytearray(2)
        for addr_off in range(size // 4):
            cc_addr = base + addr_off
            iface.read_into(cc_addr, buf)
            raw_value = struct.unpack(REG_RAW_FMT, buf)[0]
            for i in range(4):
                bitpos = 4 * i
                cc = (raw_value & (0xF << bitpos)) >> bitpos
                yield twos_complement(4, cc)
