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
        # event_loop.create_task(self.print_mem_usage())
        event_loop.run_forever()

    async def display_images(self):
        display_size = DISPLAY.get_bounds()

        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image_buf)
        pixmap.update_rect(Rect(0, 0, *display_size))
        pixmap.draw_dummy(DISPLAY)

        ui_height = int(round(pixmap.draw_rect.y))
        text_temp_ret = TextBox(
            Rect(0, 5, 60, ui_height - 10),
            "---°C",
            bg = COLOR_UI_BG, 
            scale = 2,
        )
        text_temp_ret.draw(DISPLAY)

        y = int(round(pixmap.draw_rect.y + pixmap.draw_rect.height)) 
        ui_height = display_size[1] - y
        text_temp_min = TextBox(
            Rect(0, y + 5, 60, ui_height - 10),
            "---°C",
            scale = 2,
        )
        text_temp_min.draw(DISPLAY)

        text_temp_max = TextBox(
            Rect(80, y + 5, 60, ui_height - 10),
            "---°C",
            scale = 2,
        )
        text_temp_max.draw(DISPLAY)

        DISPLAY.update()

        # use 5/95th percentile to filter outliers
        threshold = 0.05
        p_low  = int(threshold*NUM_ROWS*NUM_COLS)
        p_high = int((1-threshold)*NUM_ROWS*NUM_COLS)

        while True:
            await self.update_event.wait()
            self.update_event.clear()

            # update max/min
            sorted_temp = sorted(zip(self.image_buf, range(NUM_ROWS*NUM_COLS)))
            min_h, min_idx = sorted_temp[p_low]
            max_h, max_idx = sorted_temp[p_high]

            self.gradient.h_scale = (min_h, max_h)
            pixmap.draw_map(DISPLAY, self.gradient)
            pixmap.draw_reticle(DISPLAY, fg=COLOR_RETICLE)

            # update reticle
            reticle_temp = self.calc_reticle_temperature()
            text_temp_ret.text = f"{reticle_temp: 2.0f}°C"
            text_temp_ret.draw(DISPLAY)
            
            # update temp scale min/max
            temp_min = self.image.calc_temperature(min_idx, self.state)
            text_temp_min.text = f"{temp_min: 2.0f}°C"
            text_temp_min.draw(DISPLAY)

            temp_max = self.image.calc_temperature(max_idx, self.state)
            text_temp_max.text = f"{temp_max: 2.0f}°C"
            text_temp_max.draw(DISPLAY)

            DISPLAY.update()

    def calc_reticle_temperature(self):
        reticle = (367, 368, 399, 400)
        temp = sum(
            self.image.calc_temperature(idx, self.state)
            for idx in reticle
        )
        return temp/4

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
            
            for idx in range(NUM_ROWS*NUM_COLS):
                self.image_buf[idx] = self.image.v_ir[idx]/self.image.alpha[idx]
            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))

    async def print_mem_usage(self):
        while True:
            await uasyncio.sleep(5)
            micropython.mem_info()
