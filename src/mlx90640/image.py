import struct
from array import array
from mlx90640.regmap import (
    Struct, 
    pix_calib_address,
    twos_complement,
)

from mlx90640.regmap import (
    NUM_ROWS,
    NUM_COLS,
    NUM_PIX,
    OCC_ROWS_ADDRESS,
    OCC_COLS_ADDRESS,
    ACC_ROWS_ADDRESS,
    ACC_COLS_ADDRESS,
    PIX_CALIB_ADDRESS,
    PIX_CALIB_PROTO,
    REGISTER_RAW_FMT,
)

def _pix_idx(row, col):
    return row * NUM_COLS + col

class Calibration:
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
        self.pix_data_raw = tuple(
            eeprom.iface.read(PIX_CALIB_ADDRESS + offset)
            for offset in range(NUM_PIX)
        )
        self.pix_offsets = array('h', self._calc_pix_offsets(eeprom))

    @staticmethod
    def _read_cc_iter(iface, base, size):
        buf = bytearray(2)
        for addr_off in range(size // 4):
            cc_addr = base + addr_off
            iface.read_into(cc_addr, buf)
            raw_value = struct.unpack(REGISTER_RAW_FMT, buf)[0]
            for i in range(4):
                bitpos = 4 * i
                cc = (raw_value & (0xF << bitpos)) >> bitpos
                yield twos_complement(4, cc)

    def _calc_pix_offsets(self, eeprom):
        offset_avg = eeprom['pix_os_average']
        occ_scale_row = (1 << eeprom['scale_occ_row'])
        occ_scale_col = (1 << eeprom['scale_occ_col'])
        occ_scale_rem = (1 << eeprom['scale_occ_rem'])

        occ_rows = tuple(self._read_cc_iter(eeprom.iface, OCC_ROWS_ADDRESS, NUM_ROWS))
        occ_cols = tuple(self._read_cc_iter(eeprom.iface, OCC_COLS_ADDRESS, NUM_COLS))

        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                idx = _pix_idx(row, col)
                pix_data = Struct(self.pix_data_raw[idx], PIX_CALIB_PROTO)

                yield (
                    offset_avg
                    + occ_rows[row] * occ_scale_row
                    + occ_cols[col] * occ_scale_col
                    + pix_data['offset'] * occ_scale_rem
                )

class ImageData:
    def __init__(self, iface, calib):
        self.iface = iface





