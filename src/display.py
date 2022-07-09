from ucollections import namedtuple
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8, PEN_RGB332, PEN_RGB565

DISPLAY = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_RGB332)

PEN_DEFAULT_BG = DISPLAY.create_pen(0, 0, 0)
PEN_PIXMAP_0 = DISPLAY.create_pen(150, 200, 245)
PEN_PIXMAP_1 = DISPLAY.create_pen(240, 240, 240)


Rect = namedtuple('Rect', ('x', 'y', 'width', 'height'))

# linear interpolation helper
class Lerp:
    def __init__(self, in_scale, out_scale):
        in_min, in_max = in_scale
        out_min, out_max = out_scale
        self._slope = (out_max - out_min)/(in_max - in_min)
        self._in0 = in_min
        self._out0 = out_min

    def __call__(self, x):
        return (x - self._out0)*self._slope + self._out0

# simple value-scale
class Gradient:
    def __init__(self, h_scale=(0, 1)):
        self.h_scale = h_scale

    @staticmethod
    def _lerp(x, in_scale, out_scale):
        m = (out_scale[1] - out_scale[0])/(in_scale[1] - in_scale[0])
        return (x - in_scale[0])*m + out_scale[0]

    def get_color(self, h):
        v = int(round(self._lerp(h, self.h_scale, (0, 255))))
        return DISPLAY.create_pen(v, v, v)


class PixMap:
    def __init__(self, width, height, buf):
        # element size
        self.width = width
        self.height = height
        if len(buf) != width * height:
            raise ValueError(f"invalid buffer size for {width}x{height} PixMap: {len(buf)}")

        self.buf = buf
        self.draw_scale = 0 # size of element in pixels
        self.draw_rect = Rect(0, 0, 0, 0)

    def update_rect(self, rect):
        self.draw_scale = min(rect.width/self.width, rect.height/self.height)
        draw_width = self.width * self.draw_scale
        draw_height = self.height * self.draw_scale

        # upper left corner
        origin_x = (rect.width - draw_width)/2.0 + rect.x
        origin_y = (rect.height - draw_height)/2.0 + rect.y
        self.draw_rect = Rect(origin_x, origin_y, draw_width, draw_height)

    def draw_dummy(self, display):
        dummy_colors = (PEN_PIXMAP_0, PEN_PIXMAP_1)
        square_size = int(round(self.draw_scale))
        for j in range(self.height):
            for i in range(self.width):
                color_idx = (i+j) % len(dummy_colors)
                display.set_pen(dummy_colors[color_idx])
                
                x = int(round(self.draw_rect.x + i*self.draw_scale))
                y = int(round(self.draw_rect.y + j*self.draw_scale))
                display.rectangle(x, y, square_size, square_size)

    def draw_map(self, display, gradient):
        square_size = int(round(self.draw_scale))
        idx = 0
        for i in range(self.width):
            for j in range(self.height):
                value = self.buf[idx]
                idx += 1
                
                display.set_pen(gradient.get_color(value))
                x = int(round(self.draw_rect.x + i*self.draw_scale))
                y = int(round(self.draw_rect.y + j*self.draw_scale))
                display.rectangle(x, y, square_size, square_size)

