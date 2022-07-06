from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8, PEN_RGB332, PEN_RGB565

DISPLAY = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_RGB332)

PEN_DEFAULT_BG = DISPLAY.create_pen(0, 0, 0)
PEN_PIXMAP_0 = DISPLAY.create_pen(150, 200, 245)
PEN_PIXMAP_1 = DISPLAY.create_pen(240, 240, 240)

def draw_pixmap_dummy(display):
    pix_colors = (PEN_PIXMAP_0, PEN_PIXMAP_1)

    sensor_w, sensor_h = (24, 32)
    display_w, display_h = display.get_bounds()

    pix_scale = min(display_w/sensor_w, display_h/sensor_h)
    width, height = sensor_w*pix_scale, sensor_h*pix_scale

    origin_x = (display_w - width)/2.0
    origin_y = (display_h - height)/2.0
    square = int(round(pix_scale))
    for j in range(sensor_h):
        for i in range(sensor_w):
            color_idx = (i+j) % len(pix_colors)
            display.set_pen(pix_colors[color_idx])
            
            x = int(round(origin_x + i*pix_scale))
            y = int(round(origin_y + j*pix_scale))
            display.rectangle(x, y, square, square)

# class PixMap:
#     def __init__(self, rect, bufsize):
#         self.bufsize = bufsize