import time
from mlx90640.regmap import (
    REGISTER_MAP,
    EEPROM_MAP,
    RegisterMap,
    CameraInterface,
)
from mlx90640.calibration import CameraCalibration, NUM_ROWS, NUM_COLS
from mlx90640.image import ImageData, read_raw_image

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

    values = (
        R0_5HZ,
        R1HZ,
        R2HZ,
        R4HZ,
        R8HZ,
        R16HZ,
        R32HZ,
        R64HZ,
    )

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

# wait 80ms + delay determined by the refresh rate
def _power_on_delay(refresh_rate):
    delay_ms = int(80 + 2*1000/refresh_rate) + 1
    time.sleep_ms(delay_ms)

def _read_wait_delay(refresh_rate):
    delay_ms = int(1000/refresh_rate)
    time.sleep_ms(delay_ms)

class DataNotAvailableError(Exception): pass

class MLX90640:
    NUM_ROWS = NUM_ROWS
    NUM_COLS = NUM_COLS

    def __init__(self, i2c, addr):
        self.iface = CameraInterface(i2c, addr)
        self.registers = RegisterMap(self.iface, REGISTER_MAP)
        self.eeprom = RegisterMap(self.iface, EEPROM_MAP, readonly=True)

        _power_on_delay(self.read_refresh_rate())
        self.calib = CameraCalibration(self.iface, self.eeprom)

    def read_refresh_rate(self):
        return RefreshRate.get_freq(self.registers['refresh_rate'])
    def set_refresh_rate(self, freq):
        self.registers['refresh_rate'] = RefreshRate.from_freq(freq)

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

    def read_ta(self, ta0 = 25.0):
        return self._delta_ta() + ta0

    def _delta_ta(self):
        # ambient temperature calculation (degC)
        # type: (self) -> float
        v_ptat = self.registers['ta_ptat']
        v_be = self.registers['ta_vbe']
        v_ptat_art = v_ptat/( v_ptat*self.calib.alpha_ptat + v_be ) * (1 << 18)

        v_ta = v_ptat_art/(1.0 + self.calib.kv_ptat*self._delta_vdd() - self.calib.ptat_25)

        # print('v_ptat: ', v_ptat)
        # print('v_be:', v_be)
        # print('v_ptat_art: ', v_ptat_art)

        return v_ta/self.calib.kt_ptat

    def read_gain(self):
        # gain calculation
        # type: (self) -> float
        return self.calib.gain / self.registers['gain']

    def has_data(self):
        return bool(self.registers['data_available'])

    def read_image(self):
        if not self.has_data():
            raise DataNotAvailableError

        pix_data = tuple(read_raw_image(self.iface))
        self.registers['data_available'] = 0

        return ImageData(
            pix_data,
            self.calib,
            self.read_gain(),
            self._delta_ta(),
            self._delta_vdd(),
        )

    def stream_images(self):
        if not self.has_data():
            raise DataNotAvailableError

        while True:
            pix_data = tuple(read_raw_image(self.iface))
            self.registers['data_available'] = 0

            yield ImageData(
                pix_data,
                self.calib,
                self.read_gain(),
                self._delta_ta(),
                self._delta_vdd(),
            )

            _read_wait_delay(self.read_refresh_rate())
            while not self.has_data():
                time.sleep_ms(10)

