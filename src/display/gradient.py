""" Selection of thermal palettes
"""

from display.driver import DISPLAY

# def _lerp(x, in_scale, out_scale):
#     m = (out_scale[1] - out_scale[0])/(in_scale[1] - in_scale[0])
#     return (x - in_scale[0])*m + out_scale[0]

# linear interpolation helper
class Lerp:
    def __init__(self, in_scale, out_scale):
        in_min, in_max = in_scale
        out_min, out_max = out_scale
        self._slope = (out_max - out_min)/(in_max - in_min)
        self._in0 = in_min
        self._out0 = out_min

    def __call__(self, x):
        return (x - self._in0)*self._slope + self._out0


class WhiteHot:
    def __init__(self, h_scale=(0, 1)):
        self.h_scale = h_scale

    @property
    def h_scale(self):
        return self._h_scale

    @h_scale.setter
    def h_scale(self, value):
        self._h_scale = value
        self._lerp = Lerp(value, (0, 255))

    def get_color(self, h):
        v = int(round(self._lerp(h)))
        return DISPLAY.create_pen(v, v, v)