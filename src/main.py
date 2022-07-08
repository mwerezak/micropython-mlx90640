from array import array
from pinmap import I2C_CAMERA
from mlx90640 import detect_camera
from mlx90640.calibration import NUM_ROWS, NUM_COLS
from display import DISPLAY, PEN_DEFAULT_BG, PixMap, Rect

DISPLAY.set_pen(PEN_DEFAULT_BG)
DISPLAY.clear()

buf = array('f', (0 for i in range(NUM_ROWS * NUM_COLS)))
pixmap = PixMap(NUM_ROWS, NUM_COLS, buf)
pixmap.update_rect(Rect(0, 0, *DISPLAY.get_bounds()))
pixmap.draw_dummy(DISPLAY)
DISPLAY.update()

camera = detect_camera(I2C_CAMERA)
im = camera.read_image()
