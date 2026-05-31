import machine
from time import sleep

LED_PIN = 25

class LED:
    def __init__(self, pin=LED_PIN):
        self._pin = machine.Pin(pin, machine.Pin.OUT)
        self.off()

    def on(self):
        self._pin.value(1)

    def off(self):
        self._pin.value(0)

    def blink(self, on_time=1, off_time=None, n=None, wait=False):
        off_time = on_time if off_time is None else off_time
        if n is None:
            while True:
                self.on()
                sleep(on_time)
                self.off()
                sleep(off_time)
        else:
            for i in range(n):
                self.on()
                sleep(on_time)
                self.off()
                if i < n - 1:
                    sleep(off_time)
            if wait:
                # Ensure the final off interval is observed when requested.
                sleep(off_time)

led = LED()
