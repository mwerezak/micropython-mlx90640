from mlx90640.regmap import (
    REGISTER_MAP,
    EEPROM_MAP,
    CameraInterface, 
    RegisterMap,
)
from mlx90640.calibration import (
    CameraCalibration,
)
from mlx90640.image import ImageData

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


class MLX90640:
    def __init__(self, i2c, addr):
        self.iface = CameraInterface(i2c, addr)
        self.registers = RegisterMap(self.iface, REGISTER_MAP)
        self.eeprom = RegisterMap(self.iface, EEPROM_MAP, readonly=True)
        self.calib = CameraCalibration(self.iface, self.eeprom)

    def read_vdd(self, vdd0 = 3.3):
        # supply voltage calculation
        # type: (self) -> float
        return self._delta_vdd() + vdd0

    def _delta_vdd(self):
        vdd_pix = self.registers['vdd_pix'] * self._adc_res_corr()
        return float(vdd_pix - self.calib.vdd_25)/self.calib.k_vdd

    def _adc_res_corr(self):
        # type: (self) -> float
        res_exp = self.calib.res_ee - self.registers['adc_resolution']
        return 2**res_exp

    def read_ta(self):
        # ambient temperature calculation (degC)
        # type: (self) -> float
        v_ptat = self.registers['ta_ptat']
        v_be = self.registers['ta_vbe']
        v_ptat_art = v_ptat/( v_ptat*self.calib.alpha_ptat + v_be ) * (1 << 18)

        v_ta = v_ptat_art/(1.0 + self.calib.kv_ptat*self._delta_vdd() - self.calib.ptat_25)

        # print('v_ptat: ', v_ptat)
        # print('v_be:', v_be)
        # print('v_ptat_art: ', v_ptat_art)

        return v_ta/self.calib.kt_ptat + 25.0

    def read_gain(self):
        # gain calculation
        # type: (self) -> float
        return self.calib.gain / self.registers['gain']

    def read_image(self):
        return ImageData(self)
