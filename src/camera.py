import math
import uasyncio
import micropython
from array import array
from uasyncio import Event
from ucollections import namedtuple

from utils import array_filled
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640.calibration import NUM_ROWS, NUM_COLS, IMAGE_SIZE, TEMP_K
from mlx90640.image import ChessPattern, InterleavedPattern

from config import Config
from display import DISPLAY, Rect, PixMap, TextBox
from display.gradient import WhiteHot
from display.palette import (
    COLOR_DEFAULT_BG,
    COLOR_UI_BG,
    COLOR_RETICLE,
)

class CameraLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self.camera.set_pattern(ChessPattern)

        self.update_event = Event()
        self.state = None
        self.image = None

        self.default = Config()
        try:
            config = Config()
            config.load('config.json')
            self.reload_config(config)
        except Exception as err:
            print(f"failed to load config: {err}")
            self.reload_config(self.default)

    def reload_config(self, config):
        self.set_refresh_rate(config.refresh_rate)
        self.gradient = config.gradient()
        self.bad_pix = config.bad_pixels
        self.min_range = config.min_scale
        self.debug = config.debug

    def set_refresh_rate(self, value):
        self.camera.refresh_rate = value
        self._refresh_period = math.ceil(1000/self.camera.refresh_rate)

    async def run(self):
        await uasyncio.sleep_ms(80 + 2 * int(self._refresh_period))
        self.camera.setup()
        self.image = self.camera.image

        tasks = [
            self.display_images(),
            self.stream_images(),
        ]
        if self.debug:
            tasks.append(self.print_mem_usage())
        await uasyncio.gather(*tasks)

    async def display_images(self):
        display_size = DISPLAY.get_bounds()

        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image.buf)
        pixmap.update_rect(Rect(0, 0, *display_size))
        pixmap.draw_dummy(DISPLAY)

        for idx in self.bad_pix:
            row, col = divmod(idx, NUM_COLS)
            DISPLAY.set_pen(COLOR_RETICLE)
            DISPLAY.rectangle(*pixmap.get_elem_rect(row, col))

        ui_height = int(round(pixmap.draw_rect.y))
        text_reticle = TextBox(
            Rect(0, 5, 80, ui_height - 10),
            "----- °C",
            scale = 2,
            bg = COLOR_UI_BG, 
        )
        text_reticle.draw(DISPLAY)

        y = int(round(pixmap.draw_rect.y + pixmap.draw_rect.height)) 
        ui_height = display_size[1] - y
        text_min_scale = TextBox(
            Rect(0, y + 5, 45, ui_height - 10),
            "---",
            scale = 2,
        )
        text_min_scale.draw(DISPLAY)

        # rect_max_temp = Rect(45, y, 45, ui_height)
        text_max_temp = TextBox(
            Rect(45, y + 5, 45, ui_height - 15),
            "-00",
            scale = 2,
            # bg = COLOR_UI_BG,
        )
        text_max_temp.draw(DISPLAY)

        text_max_scale = TextBox(
            Rect(90, y + 5, 45, ui_height - 10),
            "---*",
            scale = 2,
        )
        text_max_scale.draw(DISPLAY)

        DISPLAY.update()

        while True:
            await self.update_event.wait()
            self.update_event.clear()

            # update max/min
            limits = self.image.calc_limits(exclude_idx=self.bad_pix)

            # update temp scale min/max
            min_temp = self._calc_temp(limits.min_idx)
            max_temp = self._calc_temp(limits.max_idx)
            # print(min_temp, max_temp)

            # dynamic scaling
            boost = 1
            scale_h = limits.max_h
            scale_temp = max_temp
            if scale_temp - min_temp < self.min_range:
                scale_temp = min_temp + self.min_range
                boost = ((scale_temp + TEMP_K)/(max_temp + TEMP_K))**4
                scale_h *= boost

            # draw pixel map
            self.gradient.h_scale = (limits.min_h, scale_h)
            pixmap.draw_map(DISPLAY, self.gradient)
            pixmap.draw_reticle(DISPLAY, fg=COLOR_RETICLE)

            # update reticle
            reticle_temp = self.calc_reticle_temperature()
            text_reticle.text = f"{reticle_temp: 2.1f} °C"
            text_reticle.draw(DISPLAY)

            # update scale text
            text_min_scale.text = f"{min_temp: 2.0f}"
            text_min_scale.draw(DISPLAY)

            if boost == 1:
                text_max_scale.text = f"{max_temp: 2.0f}"
                DISPLAY.set_pen(COLOR_DEFAULT_BG)
                DISPLAY.rectangle(*text_max_temp.rect)
            else:
                text_max_scale.text = f"{scale_temp: 2.0f}*"
                text_max_temp.text = f"{max_temp: 2.0f}"
                text_max_temp.draw(DISPLAY)

            text_max_scale.draw(DISPLAY)

            DISPLAY.update()

    def _calc_temp(self, idx):
        return self.image.calc_temperature(idx, self.state)

    def _calc_temp_ext(self, idx):
        return self.image.calc_temperature_ext(idx, self.state)

    def calc_reticle_temperature(self):
        reticle = (367, 368, 399, 400)
        temp = sum(self._calc_temp_ext(idx) for idx in reticle)
        return temp/4

    async def wait_for_data(self):
        await uasyncio.wait_for_ms(self._wait_inner(), int(self._refresh_period))

    async def _wait_inner(self):
        while not self.camera.has_data:
            await uasyncio.sleep_ms(50)

    async def stream_images(self):
        sp = 0
        while True:
            await self.wait_for_data()
            
            self.camera.read_image(sp)

            self.state = self.camera.read_state()
            self.image = self.camera.process_image(sp, self.state)
            self.image.interpolate_bad_pixels(self.bad_pix)
            sp = int(not sp)

            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))

    async def print_mem_usage(self):
        while True:
            await uasyncio.sleep(5)
            micropython.mem_info()
