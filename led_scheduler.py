import time
from lib.led import led


class LEDScheduler:
    """Non-blocking LED pattern scheduler for asynchronous status indicators.

    Instead of blocking with blink(), the scheduler maintains state and
    timing, allowing the main loop to call update() periodically without
    hanging.
    """

    def __init__(self):
        self.active_pattern = None
        self.pattern_start_time = 0
        self.pattern_state = 0

    def _pattern_boot(self, elapsed):
        """Boot pattern: two fast pulses."""
        cycle_time = 1.0  # Full on+off cycle = 1 second (0.5 on, 0.5 off)
        pattern_duration = 2.0
        if elapsed > pattern_duration:
            return False
        phase = int((elapsed % cycle_time) * 2)  # 0 = on, 1 = off
        led.on() if phase == 0 else led.off()
        return True

    def _pattern_wifi_connecting(self):
        """WiFi connecting: steady blink (1s on, 1s off)."""
        elapsed = time.time() - self.pattern_start_time
        cycle_time = 2.0  # 1s on + 1s off = 2s total
        phase = int((elapsed % cycle_time) * 0.5)  # 0 = on, 1 = off
        led.on() if phase == 0 else led.off()
        return True  # Runs indefinitely until cancelled

    def _pattern_wifi_connected(self):
        """WiFi connected: two short pulses, then off."""
        elapsed = time.time() - self.pattern_start_time
        if elapsed < 0.3:
            led.on()
        elif elapsed < 0.5:
            led.off()
        elif elapsed < 0.8:
            led.on()
        elif elapsed < 1.0:
            led.off()
        else:
            led.off()
            return False
        return True

    def _pattern_mqtt_connected(self):
        """MQTT connected: single short pulse."""
        elapsed = time.time() - self.pattern_start_time
        if elapsed < 0.2:
            led.on()
        elif elapsed < 0.5:
            led.off()
        else:
            led.off()
            return False
        return True

    def _pattern_mqtt_error(self):
        """MQTT error: rapid triple blink."""
        elapsed = time.time() - self.pattern_start_time
        pattern_duration = 1.8
        if elapsed > pattern_duration:
            led.off()
            return False
        cycle_time = 0.3  # 0.15s on, 0.15s off
        phase = int((elapsed % cycle_time) * 2)  # 0 = on, 1 = off
        led.on() if phase == 0 else led.off()
        return True

    def _pattern_ota(self):
        """OTA in progress: fast on-off blink."""
        elapsed = time.time() - self.pattern_start_time
        cycle_time = 0.2  # 0.1s on, 0.1s off
        phase = int((elapsed % cycle_time) * 2)  # 0 = on, 1 = off
        led.on() if phase == 0 else led.off()
        return True  # Runs until cancelled

    def _pattern_error(self):
        """Error state: slow ominous blink."""
        elapsed = time.time() - self.pattern_start_time
        cycle_time = 1.0  # 0.5s on, 0.5s off
        phase = int((elapsed % cycle_time) * 2)  # 0 = on, 1 = off
        led.on() if phase == 0 else led.off()
        return True  # Runs indefinitely until cancelled

    def start_pattern(self, pattern_name):
        """Start a non-blocking LED pattern by name."""
        self.active_pattern = pattern_name
        self.pattern_start_time = time.time()
        self.pattern_state = 0

    def stop_pattern(self):
        """Stop the current pattern and turn off LED."""
        self.active_pattern = None
        led.off()

    def update(self):
        """Call this periodically from main loop to update LED state."""
        if self.active_pattern is None:
            return

        elapsed = time.time() - self.pattern_start_time

        # Dispatch to appropriate pattern handler
        if self.active_pattern == "boot":
            keep_running = self._pattern_boot(elapsed)
        elif self.active_pattern == "wifi_connecting":
            keep_running = self._pattern_wifi_connecting()
        elif self.active_pattern == "wifi_connected":
            keep_running = self._pattern_wifi_connected()
        elif self.active_pattern == "mqtt_connected":
            keep_running = self._pattern_mqtt_connected()
        elif self.active_pattern == "mqtt_error":
            keep_running = self._pattern_mqtt_error()
        elif self.active_pattern == "ota":
            keep_running = self._pattern_ota()
        elif self.active_pattern == "error":
            keep_running = self._pattern_error()
        else:
            keep_running = False

        # Auto-stop if pattern finished
        if not keep_running:
            self.stop_pattern()


# Global scheduler instance
led_scheduler = LEDScheduler()
