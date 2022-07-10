from ucollections import namedtuple

from display.driver import DISPLAY

from display.palette import (
    COLOR_DEFAULT_BG,
    COLOR_DEFAULT_FG,
    COLOR_PIXMAP_0,
    COLOR_PIXMAP_1,
)


DISPLAY.set_pen(COLOR_DEFAULT_BG)
DISPLAY.clear()

Rect = namedtuple('Rect', ('x', 'y', 'width', 'height'))

class TextBox:
    def __init__(self, rect, text, *, fg=COLOR_DEFAULT_FG, bg=COLOR_DEFAULT_BG, font='bitmap6', **kwargs):
        self.rect = rect
        self.text = text
        self.fg = fg
        self.bg = bg
        self.font = font
        self.kwargs = kwargs

    def draw(self, display):
        display.set_pen(self.bg)
        display.rectangle(*self.rect)

        display.set_pen(self.fg)
        display.set_font(self.font)
        display.text(self.text, self.rect.x, self.rect.y, wordwrap=self.rect.width, **self.kwargs)

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
        self.square_size = int(round(self.draw_scale))
        draw_width = self.width * self.draw_scale
        draw_height = self.height * self.draw_scale

        # upper left corner
        origin_x = (rect.width - draw_width)/2.0 + rect.x
        origin_y = (rect.height - draw_height)/2.0 + rect.y
        self.draw_rect = Rect(origin_x, origin_y, draw_width, draw_height)

    def draw_dummy(self, display):
        dummy_colors = (COLOR_PIXMAP_0, COLOR_PIXMAP_1)
        square_size = int(round(self.draw_scale))
        for j in range(self.height):
            for i in range(self.width):
                color_idx = (i+j) % len(dummy_colors)
                display.set_pen(dummy_colors[color_idx])
                
                x = int(round(self.draw_rect.x + i*self.draw_scale))
                y = int(round(self.draw_rect.y + j*self.draw_scale))
                display.rectangle(x, y, square_size, square_size)

    def get_elem_rect(self, i, j):
        x = int(round(self.draw_rect.x + i*self.draw_scale))
        y = int(round(self.draw_rect.y + j*self.draw_scale))
        return Rect(x, y, self.square_size, self.square_size)

    def draw_map(self, display, gradient):
        idx = 0
        for i in range(self.width):
            for j in range(self.height):
                value = self.buf[idx]
                idx += 1
                
                display.set_pen(gradient.get_color(value))
                display.rectangle(*self.get_elem_rect(i, j))

    def draw_reticle(self, display, *, fg=COLOR_DEFAULT_FG, scale=1):
        display.set_pen(fg)
        half_size = self.draw_scale * scale

        center_x = self.draw_rect.width/2.0 + self.draw_rect.x
        center_y = self.draw_rect.height/2.0 + self.draw_rect.y
        display.line(
            int(round(center_x - half_size)), int(round(center_y + half_size)),
            int(round(center_x + half_size)), int(round(center_y + half_size)),
        )
        display.line(
            int(round(center_x - half_size)), int(round(center_y - half_size)),
            int(round(center_x + half_size)), int(round(center_y - half_size)),
        )
        display.line(
            int(round(center_x - half_size)), int(round(center_y - half_size)),
            int(round(center_x - half_size)), int(round(center_y + half_size)),
        )
        display.line(
            int(round(center_x + half_size)), int(round(center_y - half_size)),
            int(round(center_x + half_size)), int(round(center_y + half_size)),
        )
