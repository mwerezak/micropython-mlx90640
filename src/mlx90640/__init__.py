from ucollections import namedtuple
from mlx90640.regmap import (
    REGISTER_MAP,
    EEPROM_MAP,
    RegisterMap,
    CameraInterface,
)
from mlx90640.calibration import CameraCalibration, NUM_ROWS, NUM_COLS
from mlx90640.image import RawImage, ProcessedImage

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
    values = tuple(range(8))

    @classmethod
    def get_freq(cls, value):
        return 2.0**(value - 1)

    @classmethod
    def from_freq(cls, freq):
        _, value = min(
            (abs(freq - cls.get_freq(value)), value)
            for value in cls.values
        )
        return value


# container for momentary state needed for image compensation
CameraState = namedtuple('CameraStat', ('vdd', 'ta', 'gain'))

class DataNotAvailableError(Exception): pass

class MLX90640:
    NUM_ROWS = NUM_ROWS
    NUM_COLS = NUM_COLS

    def __init__(self, i2c, addr):
        self.iface = CameraInterface(i2c, addr)
        self.registers = RegisterMap(self.iface, REGISTER_MAP)
        self.eeprom = RegisterMap(self.iface, EEPROM_MAP, readonly=True)
        self.calib = None
        self.raw = None

    def read_calibration(self):
        self.calib = CameraCalibration(self.iface, self.eeprom)
        self.raw = RawImage()

    def read_refresh_rate(self):
        return RefreshRate.get_freq(self.registers['refresh_rate'])
    def set_refresh_rate(self, freq):
        self.registers['refresh_rate'] = RefreshRate.from_freq(freq)

    def read_vdd(self):
        # supply voltage calculation (delta Vdd)
        # type: (self) -> float
        vdd_pix = self.registers['vdd_pix'] * self._adc_res_corr()
        return float(vdd_pix - self.calib.vdd_25)/self.calib.k_vdd

    def _adc_res_corr(self):
        # type: (self) -> float
        res_exp = self.calib.res_ee - self.registers['adc_resolution']
        return 2**res_exp

    def read_ta(self):
        # ambient temperature calculation (delta Ta in degC)
        # type: (self) -> float
        v_ptat = self.registers['ta_ptat']
        v_be = self.registers['ta_vbe']
        v_ptat_art = v_ptat/( v_ptat*self.calib.alpha_ptat + v_be ) * (1 << 18)

        v_ta = v_ptat_art/(1.0 + self.calib.kv_ptat*self.read_vdd() - self.calib.ptat_25)

        # print('v_ptat: ', v_ptat)
        # print('v_be:', v_be)
        # print('v_ptat_art: ', v_ptat_art)

        return v_ta/self.calib.kt_ptat

    def read_gain(self):
        # gain calculation
        # type: (self) -> float
        return self.calib.gain / self.registers['gain']

    def read_state(self):
        return CameraState(
            vdd = self.read_vdd(),
            ta = self.read_ta(),
            gain = self.read_gain(),
        )

    def has_data(self):
        return bool(self.registers['data_available'])

    def read_image(self):
        if not self.has_data():
            raise DataNotAvailableError

        self.raw.read(self.iface)
        self.registers['data_available'] = 0
        return self.raw

    def process_image(self, raw_img=None):
        raw_img = raw_img or self.raw
        return ProcessedImage(raw_img.pix, self.calib, self.read_state())
