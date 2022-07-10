import math
import uasyncio
import micropython
from array import array
from uasyncio import Event
from ucollections import namedtuple

from utils import array_filled
from pinmap import I2C_CAMERA

import mlx90640
from mlx90640 import NUM_ROWS, NUM_COLS, TEMP_K
from mlx90640.image import ChessPattern, InterleavedPattern

from config import Config
from display import DISPLAY, Rect, PixMap, TextBox
from display.palette import (
    COLOR_DEFAULT_BG,
    COLOR_UI_BG,
    COLOR_RETICLE,
)

ScaleLimits = namedtuple('ScaleLimits', ('min_h', 'max_h', 'min_idx', 'max_idx'))

_IDX_NEIGHBOURS = tuple(
    row * NUM_COLS + col
    for row in (-1, 0, 1)
    for col in (-1, 0, 1)
    if row != 0 or col != 0
)

class CameraLoop:
    def __init__(self):
        self.camera = mlx90640.detect_camera(I2C_CAMERA)
        self.camera.set_pattern(ChessPattern)

        self.update_event = Event()
        self.image_buf = array('f', (0 for i in range(NUM_ROWS*NUM_COLS)))
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

    def run(self):
        event_loop = uasyncio.get_event_loop()
        event_loop.create_task(self.display_images())
        event_loop.create_task(self.stream_images())
        if self.debug:
            event_loop.create_task(self.print_mem_usage())
        
        try:
            event_loop.run_forever()
        except:
            DISPLAY.set_pen(COLOR_DEFAULT_BG)
            DISPLAY.clear()

    async def display_images(self):
        display_size = DISPLAY.get_bounds()

        pixmap = PixMap(NUM_ROWS, NUM_COLS, self.image_buf)
        pixmap.update_rect(Rect(0, 0, *display_size))
        pixmap.draw_dummy(DISPLAY)

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

        buf_size = NUM_ROWS*NUM_COLS

        while True:
            await self.update_event.wait()
            self.update_event.clear()

            # update max/min
            limits = self._calc_limits(self.image_buf, exclude_idx=self.bad_pix)

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

            # draw thermal image
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
        to = self.image.calc_temperature(idx, self.state)
        return self.image.calc_temperature_ext(idx, self.state, to)

    @staticmethod
    def _calc_limits(image_buf, *, exclude_idx=()):
        # find min/max in place to keep mem usage down
        min_h, min_idx = None, None
        max_h, max_idx = None, None
        for idx, h in enumerate(image_buf):
            if idx in exclude_idx:
                continue
            if min_h is None or h < min_h:
                min_h, min_idx = h, idx
            if max_h is None or h > max_h:
                max_h, max_idx = h, idx
        return ScaleLimits(min_h, max_h, min_idx, max_idx)

    @staticmethod
    def _interpolate_bad_pixels(image_buf, bad_pix):
        buf_size = len(image_buf)
        for bad_idx in bad_pix:
            count = 0
            total = 0
            for offset in _IDX_NEIGHBOURS:
                idx = bad_idx + offset
                if idx in range(buf_size) and idx not in bad_pix:
                    count += 1
                    total += image_buf[idx]
            if count > 0:
                image_buf[bad_idx] = total/count

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
            self._interpolate_bad_pixels(self.image_buf, self.bad_pix)

            self.update_event.set()

            await uasyncio.sleep_ms(int(self._refresh_period * 0.8))

    async def print_mem_usage(self):
        while True:
            await uasyncio.sleep(5)
            micropython.mem_info()
