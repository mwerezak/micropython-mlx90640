from ucollections import namedtuple
from mlx90640.regmap import (
    REGISTER_MAP,
    EEPROM_MAP,
    RegisterMap,
    CameraInterface,
)
from mlx90640.calibration import CameraCalibration, NUM_ROWS, NUM_COLS
from mlx90640.image import RawImage, ProcessedImage, Subpage, get_pattern_by_id

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
            (abs(freq - cls.get_freq(v)), v)
            for v in cls.values
        )
        return value

# container for momentary state needed for image compensation
CameraState = namedtuple('CameraState', ('vdd', 'ta', 'gain', 'gain_cp'))

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
        self.image = None
        self.last_read = None

    def setup(self, *, calib=None, raw=None, image=None):
        self.calib = calib or CameraCalibration(self.iface, self.eeprom)
        self.raw = raw or RawImage()
        self.image = image or ProcessedImage(self.calib)

    @property
    def refresh_rate(self):
        return RefreshRate.get_freq(self.registers['refresh_rate'])
    @refresh_rate.setter
    def refresh_rate(self, freq):
        self.registers['refresh_rate'] = RefreshRate.from_freq(freq)

    def get_pattern(self):
        return get_pattern_by_id(self.registers['read_pattern'])
    def set_pattern(self, pat):
        self.registers['read_pattern'] = pat.pattern_id

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
        v_ptat_art = v_ptat/(v_ptat*self.calib.alpha_ptat + v_be) * 262144

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
        gain = self.read_gain()
        cp_sp_0 = gain * self.registers['cp_sp_0']
        cp_sp_1 = gain * self.registers['cp_sp_1']
        return CameraState(
            vdd = self.read_vdd(),
            ta = self.read_ta(),
            gain = gain,
            gain_cp = (cp_sp_0, cp_sp_1),
        )

    @property
    def has_data(self):
        return bool(self.registers['data_available'])

    @property
    def last_subpage(self):
        return self.registers['last_subpage']

    def read_image(self, sp_id = None):
        if not self.has_data:
            raise DataNotAvailableError
        
        if sp_id is None:
            sp_id = self.last_subpage

        subpage = Subpage(self.get_pattern(), sp_id)
        self.last_read = subpage

        # print(f"read SP {subpage.id}")
        self.raw.read(self.iface, subpage.sp_range())
        self.registers['data_available'] = 0
        return self.raw

    def process_image(self, sp_id = None, state = None):
        if self.last_read is None:
            raise DataNotAvailableError

        subpage = self.last_read
        if sp_id is not None:
            subpage.id = sp_id

        state = state or self.read_state()

        # print(f"process SP {subpage.id}")
        raw_data = ((idx, self.raw[idx]) for idx in subpage.sp_range())
        self.image.update(raw_data, subpage, state)
        return self.image
