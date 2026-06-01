import machine
from time import sleep

class LED:
    def __init__(self, pin="LED"):
        self._pin = machine.Pin(pin, machine.Pin.OUT)
        self.off()

    def on(self):
        self._pin.value(1)

    def off(self):
        self._pin.value(0)

    def blink(self, on_time=1, off_time=None, n=None, wait=False):
        """Blink the LED. Uses integer seconds for timings to avoid float issues.

        on_time and off_time are integers (seconds). If n is None, blink
        indefinitely (blocking). If wait=True, wait the final off interval.
        """
        if off_time is None:
            off_time = on_time

        if n is None:
            while True:
                self.on()
                sleep(int(on_time))
                self.off()
                sleep(int(off_time))
        else:
            for i in range(int(n)):
                self.on()
                sleep(int(on_time))
                self.off()
                if i < int(n) - 1:
                    sleep(int(off_time))
            if wait:
                sleep(int(off_time))

    # Convenience patterns for status indications (blocking short patterns)
    def pattern_boot(self):
        self.blink(on_time=1, off_time=1, n=2)

    def pattern_wifi_connecting(self):
        self.blink(on_time=1, off_time=1, n=4)

    def pattern_wifi_connected(self):
        self.on()
        sleep(2)
        self.off()

    def pattern_mqtt_connected(self):
        self.on()
        sleep(1)
        self.off()

    def pattern_mqtt_error(self):
        self.blink(on_time=1, off_time=1, n=6)

    def pattern_ota(self):
        self.blink(on_time=1, off_time=0, n=10)

    def pattern_error(self):
        self.blink(on_time=1, off_time=1, n=10)


led = LED()
