from utils import (
    Struct, 
    StructProto,
    field_desc,
    Array2D,
)
from mlx90640.regmap import REG_SIZE

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
    buf = bytearray(REG_SIZE)
    struct = Struct(buf, CC_PROTO)
    for addr_off in range(size // 4):
        cc_addr = base + addr_off
        iface.read_into(cc_addr, buf)
        yield struct['0']
        yield struct['1']
        yield struct['2']
        yield struct['3']

def read_occ_rows(iface):
    return _read_cc_iter(iface, OCC_ROWS_ADDRESS, NUM_ROWS)

def read_occ_cols(iface):
    return _read_cc_iter(iface, OCC_COLS_ADDRESS, NUM_COLS)


PIX_CALIB_PROTO = StructProto((
    field_desc('offset',  6, 10, signed=True),
    field_desc('alpha',   6,  4),
    field_desc('kta',     3,  1, signed=True),
    field_desc('outlier', 1,  0),
))

PIX_CALIB_ADDRESS = const(0x2440)


class PixelCalibrationData:
    def __init__(self, iface):
        pix_count = NUM_ROWS * NUM_COLS
        self._data = bytearray(pix_count * REG_SIZE)
        for idx in range(pix_count):
            offset = idx * REG_SIZE
            iface.read_into(PIX_CALIB_ADDRESS + offset, self._data[offset:offset+REG_SIZE])

    def get_data(self, row, col):
        # type: (row, col) -> Struct
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
        self.alpha_ptat = eeprom['k_ptat'] / 4.0 + 8.0

        # gain
        self.gain = eeprom['gain']

        # pixel calibration data
        self.pix_data = PixelCalibrationData(iface)
        self.pix_os_ref = Array2D.from_iter('h', NUM_COLS, self._calc_pix_os_ref(iface, eeprom))

        # IR data compensation
        self.kta_scale_1 = 1 << (eeprom['kta_scale_1'] + 8)
        self.kta_scale_2 = 1 << eeprom['kta_scale_2']
        self.pix_kta = Array2D.from_iter('f', NUM_COLS, self._calc_pix_kta(eeprom))

        self.kv_scale = 1 << eeprom['kv_scale']
        self.kv_avg = (
            # index by [row % 2][col % 2]
            (eeprom['kv_avg_re_ce']/self.kv_scale, eeprom['kv_avg_re_co']/self.kv_scale),
            (eeprom['kv_avg_ro_ce']/self.kv_scale, eeprom['kv_avg_ro_co']/self.kv_scale),
        )
        
        # IR gradient compensation
        offset_cp_sp_0 = eeprom['offset_cp_sp_0']
        offset_cp_sp_1 = offset_cp_sp_0 + eeprom['cp_offset_delta']
        self.offset_cp = (offset_cp_sp_0, offset_cp_sp_1)

        self.kta_cp = eeprom['kta_cp'] / self.kta_scale_1
        self.kv_cp = eeprom['kv_cp'] / self.kv_scale

        self.tgc = eeprom['tgc'] / 32.0

        # interleaved pattern
        self.il_chess_c1 = eeprom['il_chess_c1'] / 16.0
        self.il_chess_c2 = eeprom['il_chess_c2'] / 2.0
        self.il_chess_c3 = eeprom['il_chess_c3'] / 8.0

    def _calc_pix_os_ref(self, iface, eeprom):
        offset_avg = eeprom['pix_os_average']
        occ_scale_row = (1 << eeprom['scale_occ_row'])
        occ_scale_col = (1 << eeprom['scale_occ_col'])
        occ_scale_rem = (1 << eeprom['scale_occ_rem'])

        occ_rows = tuple(read_occ_rows(iface))
        occ_cols = tuple(read_occ_cols(iface))

        for row, col in Array2D.range(NUM_ROWS, NUM_COLS):
            yield (
                offset_avg
                + occ_rows[row] * occ_scale_row
                + occ_cols[col] * occ_scale_col
                + self.pix_data.get_data(row, col)['offset'] * occ_scale_rem
            )

    def _calc_pix_kta(self, eeprom):
        # index by [row % 2][col % 2]
        kta_avg = (
            (eeprom['kta_avg_re_ce'], eeprom['kta_avg_re_co']),
            (eeprom['kta_avg_ro_ce'], eeprom['kta_avg_ro_co']),
        )

        for row, col in Array2D.range(NUM_ROWS, NUM_COLS):
            kta_ee = self.pix_data.get_data(row, col)['kta']
            kta_rc = kta_avg[row % 2][col % 2]
            yield (kta_rc + kta_ee * self.kta_scale_2)/self.kta_scale_1
