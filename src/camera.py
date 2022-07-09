import math
import uasyncio
from uasyncio import Event
from array import array

from utils import array_filled
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS
from mlx90640.image import ChessPattern, InterleavedPattern
from display import DISPLAY, PixMap, Rect, Gradient, TextBox

PEN_RETICLE = DISPLAY.create_pen(77, 255, 124)

class CameraLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)
        
        self.camera.set_pattern(ChessPattern)
        # self.camera.set_pattern(InterleavedPattern)
        self.set_refresh_rate(8)

        self.update_event = Event()
        self.image_buf = array('f', (0 for i in range(NUM_ROWS*NUM_COLS)))
        self.temp_text = " -- °C"

    def set_refresh_rate(self, value):
        self.camera.refresh_rate = value
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)

    def run(self):
        event_loop = uasyncio.get_event_loop()
        event_loop.create_task(self.display_images())
        event_loop.create_task(self.stream_images())
        event_loop.run_forever()

    async def display_images(self):
        gradient = Gradient()

        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image_buf)
        pixmap.update_rect(Rect(0, 0, *DISPLAY.get_bounds()))
        pixmap.draw_dummy(DISPLAY)

        ui_bg = DISPLAY.create_pen(28, 55, 56)
        temp_out = TextBox(Rect(0, 0, 80, 30), self.temp_text, bg=ui_bg, scale=3)
        temp_out.draw(DISPLAY)

        DISPLAY.update()

        while True:
            await self.update_event.wait()
            self.update_event.clear()
            gradient.h_scale = (min(self.image_buf), max(self.image_buf))
            pixmap.draw_map(DISPLAY, gradient)
            pixmap.draw_reticle(DISPLAY, fg=PEN_RETICLE)

            temp_out.text = self.temp_text
            temp_out.draw(DISPLAY)

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
            state = self.camera.read_state()
            im = self.camera.process_image(sp, state)
            sp = int(not sp)
            
            for idx in range(len(self.image_buf)):
                self.image_buf[idx] = im.v_ir[idx]/im.alpha[idx]

            temp = 0
            for row in (11, 12):
                for col in (15,16):
                    idx = row * 32 + col
                    temp += im.calc_temperature(idx, state)
            temp /= 4
            self.temp_text = f"{temp: 2.0f} °C"

            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))
