import uasyncio
from camera import CameraLoop
main = CameraLoop()
uasyncio.run(main.run())