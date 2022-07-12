import time
time.sleep(2)
import uasyncio
from camera import CameraLoop
main = CameraLoop()
uasyncio.run(main.run())