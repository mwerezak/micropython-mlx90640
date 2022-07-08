from bitutils import Array2D
from pinmap import I2C_CAMERA
import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS
from display import DISPLAY, PEN_DEFAULT_BG, PixMap, Rect, Gradient

DISPLAY.set_pen(PEN_DEFAULT_BG)
DISPLAY.clear()

values = ( 
    0 for row, col in Array2D.index_range(NUM_ROWS, NUM_COLS)
)
buf = Array2D('f', NUM_COLS, values)

pixmap = PixMap(NUM_ROWS, NUM_COLS, buf)
pixmap.update_rect(Rect(0, 0, *DISPLAY.get_bounds()))
pixmap.draw_dummy(DISPLAY)
DISPLAY.update()

camera = mlx90640.detect_camera(I2C_CAMERA)
camera.set_refresh_rate(4)
camera.read_calibration()

for im in camera.stream_images():
    buf[:] = im.pixbuf
    gradient = Gradient((min(buf), max(buf)))
    pixmap.draw_map(DISPLAY, gradient)
    DISPLAY.update()