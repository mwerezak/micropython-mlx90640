from mlx90640.regmap import (
    REGISTER_MAP,
    EEPROM_MAP,
    CameraInterface, 
    RegisterMap,
)

class CameraDetectError(Exception): pass

def detect_camera(i2c):
    """Detects the camera with the assumption that it is the only device on the I2C interface"""
    scan = i2c.scan()
    if len(scan) == 0:
        raise CameraDetectError("no camera detected")
    if len(scan) > 1:
        raise CameraDetectError("multiple devices detected on I2C interface")
    cam_addr = scan[0]
    return MLX90640(i2c, cam_addr)

class RefreshRate:
    R0_5HZ = const(0x0)
    R1HZ   = const(0x1)
    R2HZ   = const(0x2)
    R4HZ   = const(0x3)
    R8HZ   = const(0x4)
    R16HZ  = const(0x5)
    R32HZ  = const(0x6)
    R64HZ  = const(0x7)


def _2s_complement(bits, value):
    if value >= (1 << (bits - 1)):
        return value - (1 << bits)
    return value


class Calibration:
    def load(self, eeprom):
        # restore VDD sensor parameters
        self.k_vdd = eeprom['k_vdd'] * (1 << 5)
        self.vdd_25 = (eeprom['vdd_25'] - 256) * (1 << 5) - (1 << 13)

        # restore Ta sensor parameters
        # kv_ptat = _2s_complement( 6, eeprom['kv_ptat']) / (1 << 12)
        # kt_ptat = _2s_complement(10, eeprom['kt_ptat']) / (1 <<  3)
        # v_ptat_25 = eeprom['ptat_25']
        # delta_v = (ram['vdd_pix'] - self.vdd_25)/




class MLX90640:
    def __init__(self, i2c, addr):
        self.iface = CameraInterface(i2c, addr)
        self.registers = RegisterMap(self.iface, REGISTER_MAP)
        self.eeprom = RegisterMap(self.iface, EEPROM_MAP)

        self.calibration = Calibration()
        self.calibration.load(self.eeprom)

    def read_vdd(self):
        # supply voltage calculation
        pass

    def _adc_res_corr(self):
        pass
