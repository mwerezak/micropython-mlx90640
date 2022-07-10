import json

from display.gradient import WhiteHot, BlackHot, Ironbow

_THERM_PALETTE = {
    'whitehot': WhiteHot,
    'blackhot': BlackHot,
    'ironbow': Ironbow,
}

class Config:
    def __init__(self):
        self.refresh_rate = 4
        self.bad_pixels = ()
        self.gradient = WhiteHot
        self.min_scale = 8
        self.debug = False

    def load(self, config_path):
        with open(config_path, 'rt') as cfg_file:
            cfg_data = json.load(cfg_file)

        if 'refresh_rate' in cfg_data:
            self.refresh_rate = int(cfg_data['refresh_rate'])
        if 'bad_pixels' in cfg_data:
            self.bad_pixels = tuple(int(idx) for idx in cfg_data['bad_pixels'])
        if 'gradient' in cfg_data:
            self.gradient = self.get_palette(cfg_data['gradient'], self.gradient)
        if 'min_scale' in cfg_data:
            self.min_scale = int(cfg_data['min_scale'])
        if 'debug' in cfg_data:
            self.debug = bool(cfg_data['debug'])

    @staticmethod
    def get_palette(name, default=Ironbow):
        return _THERM_PALETTE.get(name, default)