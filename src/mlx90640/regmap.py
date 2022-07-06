import struct
from ucollections import namedtuple

import uctypes
from uctypes import (
    INT8,
    INT16,
    UINT8, 
    UINT16,
    BFUINT16, 
    BF_POS, 
    BF_LEN, 
    BIG_ENDIAN,
)


def _2s_complement(bits, value):
    if value >= (1 << (bits - 1)):
        return value - (1 << bits)
    return value


REGISTER_RAW_FMT = const('>H')  # I2C registers are 16-bit big-endian

FD_BYTE = object()
FD_WORD = object()

FieldDesc = namedtuple('FieldDesc', ('name', 'layout', 'use_2s_compl'))
def field_desc(name, bits, pos=0, signed=False):
    if bits is FD_WORD:
        layout = 0 | (INT16 if signed else UINT16)
        return FieldDesc(name, layout, None)
    
    if bits is FD_BYTE:
        layout = pos | (INT8 if signed else UINT8)
        return FieldDesc(name, layout, None)

    layout = 0 | BFUINT16 | pos << BF_POS | bits << BF_LEN
    return FieldDesc(name, layout, bits if signed else None)


REGISTER_MAP = {
    # Status Register
    0x8000 : (
        field_desc('last_subpage',      3, 0),
        field_desc('data_available',    1, 3),
        field_desc('overwrite_enable',  1, 4),
    ),

    # Control Register 1
    0x800D : (
        field_desc('subpage_enable',    1,  0),
        field_desc('data_hold',         1,  2),
        field_desc('subpage_repeat',    1,  3),
        field_desc('repeat_select',     3,  4),
        field_desc('refresh_rate',      3,  7),
        field_desc('adc_resolution',    2, 10),
        field_desc('read_pattern',      1, 12),
    ),

    # I2C Config Register
    0x800F : (
        field_desc('fmplus_enable',     1, 0),
        field_desc('i2c_levels',        1, 1),
        field_desc('sda_current_limit', 1, 2),
    ),

    # I2C Address
    0x8010 : field_desc('i2c_address',  FD_BYTE, 1),
    0x0700 : field_desc('ta_vbe',       FD_WORD, signed=True),
    0x0708 : field_desc('cp_sp_0',      FD_WORD, signed=True),
    0x070A : field_desc('gain',         FD_WORD, signed=True),
    0x0720 : field_desc('ta_ptat',      FD_WORD, signed=True),
    0x0728 : field_desc('cp_sp_1',      FD_WORD, signed=True),
    0x072A : field_desc('vdd_pix',      FD_WORD, signed=True),
}

# Calibration Data

# From table on page 21
EEPROM_MAP = {
    0x2410 : (
        field_desc('k_ptat',         4, 12),
        field_desc('scale_occ_row',  4,  8),
        field_desc('scale_occ_col',  4,  4),
        field_desc('scale_occ_rem',  4,  0),
    ),
    0x2411 : field_desc('pix_os_average', FD_WORD, signed=True),
    0x2420 : (
        field_desc('alpha_scale',    4, 12, signed=True),
        field_desc('scale_acc_row',  4,  8, signed=True),
        field_desc('scale_acc_col',  4,  4, signed=True),
        field_desc('scale_acc_rem',  4,  0, signed=True),
    ),
    0x2421 : field_desc('pix_sensitivity_average', FD_WORD),
    0x2430 : field_desc('gain',    FD_WORD, signed=True),
    0x2431 : field_desc('ptat_25', FD_WORD, signed=True),
    0x2432 : (
        field_desc('kv_ptat',  6, 10, signed=True),
        field_desc('kt_ptat', 10,  0, signed=True),
    ),
    0x2433 : (
        field_desc('kv_vdd', FD_BYTE, 1, signed=True),
        field_desc('vdd_25', FD_BYTE, 0, signed=True),
    ),
    0x2434 : (
        field_desc('kv_avg_ro_co', 4, 12, signed=True),
        field_desc('kv_avg_re_co', 4,  8, signed=True),
        field_desc('kv_avg_ro_ce', 4,  4, signed=True),
        field_desc('kv_avg_re_ce', 4,  0, signed=True),
    ),
    0x2435 : (
        field_desc('il_chess_c3', 5, 11, signed=True),
        field_desc('il_chess_c2', 5,  6, signed=True),
        field_desc('il_chess_c1', 6,  0, signed=True),
    ),
    0x2436 : (
        field_desc('kta_avg_ro_co', FD_BYTE, 1, signed=True),
        field_desc('kta_avg_re_co', FD_BYTE, 0, signed=True),
    ),
    0x2437 : (
        field_desc('kta_avg_ro_ce', FD_BYTE, 1, signed=True),
        field_desc('kta_avg_re_ce', FD_BYTE, 0, signed=True),
    ),
    0x2438 : (
        field_desc('res_ctrl_cal', 4, 12),
        field_desc('kv_scale',     4,  8),
        field_desc('kta_scale_1',  4,  4),
        field_desc('kta_scale_2',  4,  0),
    ),
    0x2439 : (
        field_desc('cp_sp_ratio',    6  10),
        field_desc('alpha_cp_sp_0', 10,  0),
    ),
    0x243A : (
        field_desc('cp_offset_delta',  6, 10, signed=True),
        field_desc('offset_cp_sp_0',  10,  0, signed=True),
    ),
    0x243B : (
        field_desc('kv_cp',  FD_BYTE, 1, signed=True),
        field_desc('kta_cp', FD_BYTE, 0, signed=True),
    ),
    0x243C : (
        field_desc('ksta',   FD_BYTE, 1, signed=True),
        field_desc('tgc',    FD_BYTE, 0),
    ),
    0x243D : (
        field_desc('ksto_2', FD_BYTE, 1, signed=True),
        field_desc('ksto_1', FD_BYTE, 0, signed=True),
    ),
    0x243E : (
        field_desc('ksto_4', FD_BYTE, 1, signed=True),
        field_desc('ksto_3', FD_BYTE, 0, signed=True),
    ),
    0x243F : (
        field_desc('step',       2, 12),
        field_desc('ct4',        4,  8),
        field_desc('ct3',        4,  4),
        field_desc('ksto_scale', 4,  0),
    ),
}

OCC_ROWS = (0x2412, 24)
OCC_COLS = (0x2418, 32)

ACC_ROWS = (0x2422, 24)
ACC_COLS = (0x2428, 32)

# used for both OCC and ACC
CC_LAYOUT = (
    field_desc('0', 4,  0, signed=True),
    field_desc('1', 4,  4, signed=True),
    field_desc('2', 4,  8, signed=True),
    field_desc('3', 4, 12, signed=True),
)

PIX_CALIB_LAYOUT = (
    field_desc('offset'   6, 10, signed=True),
    field_desc('alpha'    6,  4),
    field_desc('kta',     3,  1, signed=True),
    field_desc('outlier', 1,  0),
)

class _Struct:
    def __init__(self, buf, layout):
        self._struct = uctypes.struct(
            uctypes.addressof(buf), layout, BIG_ENDIAN
        )
    def __getitem__(self, name):
        return getattr(self._struct, name)
    def __setitem__(self, name, value):
        setattr(self._struct, name, value)


class CameraInterface:
    def __init__(self, i2c, addr):
        self.i2c = i2c   # HW interface
        self.addr = addr # device address

    ## raw register read/write

    def read(self, mem_addr):
        return self.i2c.readfrom_mem(self.addr, mem_addr, 2, addrsize=16)
    def read_into(self, mem_addr, buf):
        self.i2c.readfrom_mem_into(self.addr, mem_addr, buf, addrsize=16)
    def write(self, mem_addr, buf):
        self.i2c.writeto_mem(self.addr, mem_addr, buf, addrsize=16)


class RegisterMap:
    def __init__(self, iface, register_map):
        # register_map should be a dict of { I2C address : uctype layout }
        self.iface = iface
        self._name_lookup = {
            name : (address, layout)
            for address, layout in register_map.items()
            for name in layout.keys()
        }

    def keys(self):
        return self._name_lookup.keys()

    def __iter__(self):
        return iter(self.keys())
    def __len__(self):
        return len(self._name_lookup)
    def __contains__(self, name):
        return name in self._name_lookup

    def __getitem__(self, name):
        address, layout = self._name_lookup[name]

        buf = self.iface.read(address)
        struct = _Struct(buf, layout)
        return struct[name]

    def __setitem__(self, name, value):
        address, layout = self._name_lookup[name]

        buf = bytearray(struct.calcsize(REGISTER_RAW_FMT))
        self.iface.read_into(address, buf)
        struct = _Struct(buf, layout)
        struct[name] = value
        self.iface.write(address, buf)