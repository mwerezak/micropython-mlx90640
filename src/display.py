from ucollections import namedtuple
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8, PEN_RGB332, PEN_RGB565

DISPLAY = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_RGB332)

PEN_DEFAULT_BG = DISPLAY.create_pen(0, 0, 0)
PEN_PIXMAP_0 = DISPLAY.create_pen(150, 200, 245)
PEN_PIXMAP_1 = DISPLAY.create_pen(240, 240, 240)


Rect = namedtuple('Rect', ('x', 'y', 'width', 'height'))

class PixMap:
    def __init__(self, width, height, buf):
        # element size
        self.width = width
        self.height = height
        if len(buf) != width * height:
            raise ValueError(f"invalid buffer size for {width}x{height} PixMap: {len(buf)}")

        self.buf = buf  # an Array2D with data
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

