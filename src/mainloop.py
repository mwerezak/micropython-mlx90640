import math
import uasyncio
from uasyncio import Event, Lock

from utils import Array2D
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS

from display import DISPLAY, PEN_DEFAULT_BG, PixMap, Rect, Gradient

class MainLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self.refresh_rate = 4

        self.update_event = Event()
        self.image_buf = Array2D.filled('f', NUM_ROWS, NUM_COLS)

    @property
    def refresh_rate(self):
        return self.camera.read_refresh_rate()

    @refresh_rate.setter
    def refresh_rate(self, value):
        self.camera.set_refresh_rate(value)
        self._refresh_period = math.ceil(1000/self.camera.read_refresh_rate())

    async def display_images(self):
        DISPLAY.set_pen(PEN_DEFAULT_BG)
        DISPLAY.clear()

        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image_buf)
        pixmap.update_rect(Rect(0, 0, *DISPLAY.get_bounds()))
        pixmap.draw_dummy(DISPLAY)
        DISPLAY.update()

        gradient = Gradient()

        while True:
            await self.update_event.wait()
            self.update_event.clear()
            gradient.h_scale = (min(self.image_buf), max(self.image_buf))
            pixmap.draw_map(DISPLAY, gradient)
            DISPLAY.update()

    async def wait_for_data(self):
        await uasyncio.wait_for_ms(self._wait_inner(), int(self._refresh_period))

    async def _wait_inner(self):
        while not self.camera.has_data():
            await uasyncio.sleep_ms(50)

    async def stream_images(self):
        await uasyncio.sleep_ms(80 + 2 * int(self._refresh_period))
        self.camera.read_calibration()

        while True:
            await self.wait_for_data()
            self.camera.read_image()
            im = self.camera.process_image()
            self.image_buf[:] = im.pix.array
            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))


main = MainLoop()
event_loop = uasyncio.get_event_loop()
event_loop.create_task(main.display_images())
event_loop.create_task(main.stream_images())
event_loop.run_forever()