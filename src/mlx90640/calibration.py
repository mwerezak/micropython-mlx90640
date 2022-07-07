import struct
from array import array
from mlx90640.regmap import (
    Struct, 
    StructProto,
    field_desc,
    REG_SIZE,
)


NUM_ROWS = const(24)
NUM_COLS = const(32)

OCC_ROWS_ADDRESS = const(0x2412)
OCC_COLS_ADDRESS = const(0x2418)

ACC_ROWS_ADDRESS = const(0x2422)
ACC_COLS_ADDRESS = const(0x2428)

CC_PROTO = StructProto((
    field_desc('0', 4,  0, signed=True),
    field_desc('1', 4,  4, signed=True),
    field_desc('2', 4,  8, signed=True),
    field_desc('3', 4, 12, signed=True),
))

def _read_cc_iter(iface, base, size):
    buf = bytearray(2)
    struct = Struct(buf, CC_PROTO)
    for addr_off in range(size // 4):
        cc_addr = base + addr_off
        iface.read_into(cc_addr, buf)
        yield struct['0']
        yield struct['1']
        yield struct['2']
        yield struct['3']


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

    @classmethod
    def index_range(cls, num_strides, stride):
        # yields i,j pairs for an Array2D with the given shape
        # useful for generating the init sequence
        for i in range(num_strides):
            for j in range(stride):
                yield i, j

    def __len__(self):
        return len(self._array)
    def __iter__(self):
        return iter(self._array)

    def iter_indexed(self):
        num_strides = (len(self._array) + self.stride - 1)//self.stride
        indices = self.index_range(num_strides, self.stride)
        for pair, value in zip(indices, self._array):
            yield pair[0], pair[1], value


class PixelCalibrationData:
    def __init__(self, iface):
        pix_count = NUM_ROWS * NUM_COLS
        self._data = bytearray(pix_count * REG_SIZE)
        for idx in range(pix_count):
            offset = idx * REG_SIZE
            iface.read_into(PIX_CALIB_ADDRESS + offset, self._data[offset:offset+REG_SIZE])

    def __getitem__(self, pixel):
        # type: (row, col) -> Struct
        row, col = pixel
        idx = row * NUM_COLS + col
        offset = idx * REG_SIZE
        return Struct(self._data[offset:offset+REG_SIZE], PIX_CALIB_PROTO)

class CameraCalibration:
    def __init__(self, iface, eeprom):
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
        self.pix_data = PixelCalibrationData(iface)
        self.pix_os_ref = Array2D('h', NUM_COLS, self._calc_pix_os_ref(eeprom))

        # IR data compensation
        self.pix_kta = Array2D('f', NUM_COLS, self._calc_pix_kta(eeprom))

        kv_scale = 1 << eeprom['kv_scale']
        self.kv_avg = (
            # index by [row % 2][col % 2]
            (eeprom['kv_avg_re_ce']/kv_scale, eeprom['kv_avg_re_co']/kv_scale),
            (eeprom['kv_avg_ro_ce']/kv_scale, eeprom['kv_avg_ro_co']/kv_scale),
        )
        

    def _calc_pix_os_ref(self, eeprom):
        offset_avg = eeprom['pix_os_average']
        occ_scale_row = (1 << eeprom['scale_occ_row'])
        occ_scale_col = (1 << eeprom['scale_occ_col'])
        occ_scale_rem = (1 << eeprom['scale_occ_rem'])

        occ_rows = tuple(_read_cc_iter(eeprom.iface, OCC_ROWS_ADDRESS, NUM_ROWS))
        occ_cols = tuple(_read_cc_iter(eeprom.iface, OCC_COLS_ADDRESS, NUM_COLS))

        for row, col in Array2D.index_range(NUM_ROWS, NUM_COLS):
            yield (
                offset_avg
                + occ_rows[row] * occ_scale_row
                + occ_cols[col] * occ_scale_col
                + self.pix_data[row, col]['offset'] * occ_scale_rem
            )

    def _calc_pix_kta(self, eeprom):
        # index by [row % 2][col % 2]
        kta_avg = (
            (eeprom['kta_avg_re_ce'], eeprom['kta_avg_re_co']),
            (eeprom['kta_avg_ro_ce'], eeprom['kta_avg_ro_co']),
        )

        kta_scale_1 = 1 << (eeprom['kta_scale_1'] + 8)
        kta_scale_2 = 1 << eeprom['kta_scale_2']
        print('kta_scale_1:', kta_scale_1)
        print('kta_scale_2:', kta_scale_2)

        for row, col in Array2D.index_range(NUM_ROWS, NUM_COLS):
            kta_ee = self.pix_data[row, col]['kta']
            kta_rc = kta_avg[row % 2][col % 2]
            yield (kta_rc + kta_ee * kta_scale_2)/kta_scale_1
