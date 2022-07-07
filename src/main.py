from display import DISPLAY, PEN_DEFAULT_BG, draw_pixmap_dummy

DISPLAY.set_pen(PEN_DEFAULT_BG)
DISPLAY.clear()
draw_pixmap_dummy(DISPLAY)
DISPLAY.update()

from pinmap import I2C_CAMERA
from mlx90640 import detect_camera

camera = detect_camera(I2C_CAMERA)
