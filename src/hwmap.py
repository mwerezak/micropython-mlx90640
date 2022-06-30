from machine import Pin, UART, I2C
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY

PIN_LED = Pin(25, Pin.OUT)

PIN_SW_A = Pin(12, Pin.IN)
PIN_SW_B = Pin(13, Pin.IN)
PIN_SW_X = Pin(14, Pin.IN)
PIN_SW_Y = Pin(15, Pin.IN)

UART_WLAN = UART(1)

PIN_I2C_SDA = Pin(10, Pin.IN, Pin.PULL_UP)
PIN_I2C_SCL = Pin(11, Pin.IN, Pin.PULL_UP)

I2C_CAMERA = I2C(
    id=1, scl=PIN_I2C_SCL, sda=PIN_I2C_SDA
)

DISPLAY = PicoGraphics(display=DISPLAY_PICO_DISPLAY)