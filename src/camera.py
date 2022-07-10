import math
import uasyncio
import micropython
from uasyncio import Event
from array import array

from utils import array_filled
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS
from mlx90640.image import ChessPattern, InterleavedPattern
from display import DISPLAY, Rect, PixMap, TextBox

from display.gradient import WhiteHot, BlackHot, Ironbow

from display.palette import (
    COLOR_UI_BG,
    COLOR_RETICLE,
)


class CameraLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self.camera.set_pattern(ChessPattern)
        # self.camera.set_pattern(InterleavedPattern)
        self.set_refresh_rate(8)

        self.update_event = Event()
        self.image_buf = array('f', (0 for i in range(NUM_ROWS*NUM_COLS)))
        
        self.temp_text = " -- °C"
        self.gradient = Ironbow()

        self.state = None
        self.image = None

    def set_refresh_rate(self, value):
        self.camera.refresh_rate = value
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)

    def run(self):
        event_loop = uasyncio.get_event_loop()
        event_loop.create_task(self.display_images())
        event_loop.create_task(self.stream_images())
        event_loop.create_task(self.print_mem_usage())
        event_loop.run_forever()

    async def display_images(self):
        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image_buf)
        pixmap.update_rect(Rect(0, 0, *DISPLAY.get_bounds()))
        pixmap.draw_dummy(DISPLAY)

        temp_ret = TextBox(
            Rect(0, 0, 80, int(round(pixmap.draw_rect.y))),
            self.temp_text,
            bg = COLOR_UI_BG,
            scale = 3,
        )
        temp_ret.draw(DISPLAY)

        DISPLAY.update()

        while True:
            await self.update_event.wait()
            self.update_event.clear()
            self.gradient.h_scale = (min(self.image_buf), max(self.image_buf))
            pixmap.draw_map(DISPLAY, self.gradient)
            pixmap.draw_reticle(DISPLAY, fg=COLOR_RETICLE)

            temp_ret.text = self.temp_text
            temp_ret.draw(DISPLAY)

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
            self.state = self.camera.read_state()
            self.image = self.camera.process_image(sp, self.state)
            sp = int(not sp)
            
            for idx in range(len(self.image_buf)):
                self.image_buf[idx] = self.image.v_ir[idx]/self.image.alpha[idx]

            temp = 0
            for row in (11, 12):
                for col in (15,16):
                    idx = row * 32 + col
                    temp += self.image.calc_temperature(idx, self.state)
            temp /= 4
            self.temp_text = f"{temp: 2.0f} °C"

            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))

    async def print_mem_usage(self):
        while True:
            await uasyncio.sleep(5)
            micropython.mem_info()
