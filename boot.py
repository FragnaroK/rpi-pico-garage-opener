import machine
import gc

# Minimal Pico W boot initialization.
# Keep boot.py small to avoid long startup time and reduce crash risk.
try:
    led = machine.Pin(25, machine.Pin.OUT)
    led.off()
except Exception:
    pass

try:
    gc.collect()
except Exception:
    pass

print('boot.py: Pico W boot completed')
