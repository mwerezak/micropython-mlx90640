# Micropython driver for the MLX90640 IR Camera

This is a micropython driver for the MLX90640 32x24 infra-red camera.

Written for and tested using a Raspberry Pi Pico (RP2040) and PicoGraphics LED display. However, the MLX90640 driver has been written to be independent of hardware (it is built on top of the the micropython I2C abstraction) and can be easily ported to another micropython-enabled device. The only requirement is floating-point support and an I2C interface to the camera.