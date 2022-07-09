import math
import uasyncio
from uasyncio import Event, Lock
from array import array

from utils import array_filled
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS
from mlx90640.image import ChessPattern, InterleavedPattern

from display import DISPLAY, PEN_DEFAULT_BG, PixMap, Rect, Gradient

class CameraLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)
        
        self.camera.set_pattern(ChessPattern)
        # self.camera.set_pattern(InterleavedPattern)
        self.set_refresh_rate(8)

        self.update_event = Event()
        self.image_buf = array('f', (0 for i in range(NUM_ROWS*NUM_COLS)))

    def set_refresh_rate(self, value):
        self.camera.refresh_rate = value
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)

    def run(self):
        event_loop = uasyncio.get_event_loop()
        event_loop.create_task(self.display_images())
        event_loop.create_task(self.stream_images())
        event_loop.run_forever()

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
        while not self.camera.has_data:
            await uasyncio.sleep_ms(50)

    async def stream_images(self):
        await uasyncio.sleep_ms(80 + 2 * int(self._refresh_period))
        self.camera.setup()

        sp = 0
        while True:
            await self.wait_for_data()
            self.camera.read_image(sp)
            im = self.camera.process_image(sp)
            sp = int(not sp)
            
            for idx in range(len(self.image_buf)):
                self.image_buf[idx] = im.v_ir[idx]/im.alpha[idx]
            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))
