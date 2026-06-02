import machine
from time import sleep, time
import network
from lib.umqtt import MQTTClient
import runtime.config as config
import gc
import random
from runtime.error_logger import error_log
from runtime.memory_monitor import memory_monitor
import runtime.mqtt_manager as mqtt_manager
import lib.ugit as ugit
from lib.led import led
from runtime.led_scheduler import led_scheduler

# --- MQTT Topics base

# --- MQTT Parameters
MQTT_SERVER = config.MQTT_SERVER
MQTT_PORT = 1883
MQTT_USER = config.MQTT_USER
MQTT_PASSWORD = config.MQTT_PASSWORD
MQTT_CLIENT_ID = b"raspberrypi_picow"
MQTT_KEEPALIVE = 60
MQTT_SSL = False
MQTT_SSL_PARAMS = {'server_hostname': MQTT_SERVER}
MQTT_TOPIC_BASE = b'pico/garage'
MQTT_TOPIC_OTA = MQTT_TOPIC_BASE + b'/ota'
MQTT_TOPIC_STATUS = MQTT_TOPIC_BASE + b'/status'

# --- Constants
RELAY_PIN = 21
PRESS_DURATION = 0.5
ACTIVE_LOW = 0
ACTIVE_HIGH = 1

# LED Pattern Constants (reused strings to save memory)
LED_BOOT = "boot"
LED_WIFI_CONNECTING = "wifi_connecting"
LED_WIFI_CONNECTED = "wifi_connected"
LED_READY = "ready"
LED_MQTT_ERROR = "mqtt_error"
LED_OTA = "ota"
LED_ERROR = "error"

# Memory management settings (optimized for constrained devices)
GC_COLLECT_INTERVAL = 8  # Reduced from 30s for more aggressive GC
MQTT_RECONNECT_BACKOFF_INIT = 5
MQTT_RECONNECT_BACKOFF_MAX = 60
MQTT_ERROR_THRESHOLD = 3

# Initialize relay pin
trigger_pin = machine.Pin(RELAY_PIN, machine.Pin.OUT, value=ACTIVE_HIGH)

# Global variables
client = None
manager = None
last_message_time = time()
last_gc_time = time()
consecutive_mqtt_errors = 0
mqtt_reconnect_backoff = MQTT_RECONNECT_BACKOFF_INIT
wdt = None

WATCHDOG_TIMEOUT_MS = 15000
# Some ports limit the WDT maximum timeout (RP2 reports ~8388 ms).
MAX_WDT_TIMEOUT_MS = 8388

def get_jitter(max_jitter_seconds=3):
    """Return a small jitter value in seconds. Works without `random` if needed."""
    try:
        return random.randint(0, max_jitter_seconds)
    except Exception:
        return int(time()) % (max_jitter_seconds + 1)

def connect_wifi(timeout=30):
    try:
        wlan = network.WLAN(network.STA_IF)
        if not wlan.active():
            wlan.active(True)

        if wlan.isconnected():
            error_log.log_error("WIFI", "WiFi already connected")
            led_scheduler.start_pattern(LED_WIFI_CONNECTED)
            return

        led_scheduler.start_pattern(LED_WIFI_CONNECTING)
        wlan.config(pm=0xa11140)
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        start = time()
        while not wlan.isconnected() and time() - start < timeout:
            led_scheduler.update()
            sleep(1)

        if not wlan.isconnected():
            error_log.log_error("WIFI", "Failed to connect to WiFi")
            led_scheduler.start_pattern(LED_ERROR)
            raise RuntimeError('Network connection failed')

        error_log.log_error("WIFI", "Successfully connected to WiFi")
        led_scheduler.start_pattern(LED_WIFI_CONNECTED)
    except Exception as e:
        error_log.log_exception(e, "connect_wifi")
        raise

def trigger_garage_door():
    try:
        trigger_pin.value(ACTIVE_LOW)
        sleep(PRESS_DURATION)
        trigger_pin.value(ACTIVE_HIGH)
        error_log.log_error("GARAGE", "Garage door triggered successfully")
    except Exception as e:
        error_log.log_exception(e, "trigger_garage_door")

def disconnect_mqtt():
    """Safely disconnect MQTT client and cleanup"""
    global client
    try:
        if manager:
            error_log.log_error("MQTT", "Disconnecting from MQTT broker")
            manager.disconnect()
            # keep client reference in sync
            client = None
    except Exception as e:
        error_log.log_exception(e, "disconnect_mqtt")
    finally:
        client = None
        gc.collect()  # Extra GC to be safe

def connect_mqtt():
    global client, consecutive_mqtt_errors, manager
    try:
        if manager is None:
            manager = mqtt_manager.MQTTManager(
                client_id=MQTT_CLIENT_ID,
                server=MQTT_SERVER,
                port=MQTT_PORT,
                user=MQTT_USER,
                password=MQTT_PASSWORD,
                keepalive=MQTT_KEEPALIVE,
                ssl=MQTT_SSL,
                ssl_params=MQTT_SSL_PARAMS,
                topic_base=MQTT_TOPIC_BASE,
            )
            manager.set_callback(on_message)

        if manager.is_connected():
            return True

        if getattr(manager, 'client', None) is not None:
            disconnect_mqtt()

        sleep(1)
        ok = manager.connect()
        if ok:
            client = manager.client
            consecutive_mqtt_errors = 0
            led_scheduler.start_pattern(LED_READY)
        else:
            led_scheduler.start_pattern(LED_MQTT_ERROR)
        return ok
    except Exception as e:
        consecutive_mqtt_errors += 1
        led_scheduler.start_pattern(LED_MQTT_ERROR)
        error_log.log_exception(e, "connect_mqtt")
        error_log.log_error("MQTT", "connect_mqtt failed", str(e))
        return False

def _publish_mqtt_status(topic, payload):
    try:
        if manager and manager.is_connected():
            manager.publish(topic, payload)
    except Exception:
        pass


def _handle_ota_request(message):
    try:
        if not isinstance(message, bytes) or message.strip().upper() != b'UPDATE':
            error_log.log_error("OTA", "Ignored OTA request: wrong payload", f"payload: {message}")
            return

        led_scheduler.start_pattern(LED_OTA)
        _publish_mqtt_status(MQTT_TOPIC_STATUS, b'OTA_STARTED')
        gc.collect()

        def _notify_complete():
            _publish_mqtt_status(MQTT_TOPIC_STATUS, b'OTA_COMPLETED')
            led_scheduler.stop_pattern()
            led.off()

        ugit.pull_all(isconnected=True, reset_after=True, on_complete=_notify_complete)
    except Exception as e:
        error_log.log_exception(e, "mqtt_ota")
        _publish_mqtt_status(MQTT_TOPIC_STATUS, b'OTA_FAILED')
        led_scheduler.start_pattern(LED_ERROR)


def on_message(topic, message):
    """Handle incoming MQTT messages"""

    try:
        error_log.log_error("MQTT", "Message received", "incoming MQTT payload")

        if topic == MQTT_TOPIC_BASE and message == b'TRIGGER':
            error_log.log_error("GARAGE", "Garage door trigger command received")
            trigger_garage_door()
        elif topic == MQTT_TOPIC_OTA:
            error_log.log_error("OTA", "OTA trigger received via MQTT")
            _handle_ota_request(message)
        else:
            error_log.log_error("MQTT", "Unknown command received", "ignored MQTT payload")
    except Exception as e:
        error_log.log_exception(e, "on_message")

def is_network_available():
    """Check if WiFi is still connected"""
    try:
        wlan = network.WLAN(network.STA_IF)
        return wlan.isconnected()
    except Exception:
        return False

def manage_memory(current_time):
    """Periodically collect garbage and monitor memory"""
    global last_gc_time
    global wdt
    
    if current_time - last_gc_time > GC_COLLECT_INTERVAL:
        gc.collect()
        last_gc_time = current_time
        memory_monitor.force_gc()
    
    memory_monitor.check_memory(current_time)

    # Feed the hardware watchdog if enabled
    try:
        if wdt is not None:
            wdt.feed()
    except Exception:
        pass

def _init_watchdog():
    """Initialize hardware watchdog; returns wdt object or None on failure"""
    try:
        wdt_timeout = WATCHDOG_TIMEOUT_MS
        if WATCHDOG_TIMEOUT_MS > MAX_WDT_TIMEOUT_MS:
            error_log.log_error(
                "WATCHDOG",
                f"Requested WDT timeout {WATCHDOG_TIMEOUT_MS}ms exceeds max {MAX_WDT_TIMEOUT_MS}ms; clamping to {MAX_WDT_TIMEOUT_MS}ms"
            )
            wdt_timeout = MAX_WDT_TIMEOUT_MS

        try:
            wdt = machine.WDT(timeout=wdt_timeout)
            error_log.log_error("WATCHDOG", f"WDT started ({wdt_timeout}ms)")
            return wdt
        except ValueError:
            try:
                wdt = machine.WDT(timeout=MAX_WDT_TIMEOUT_MS)
                error_log.log_error("WATCHDOG", f"WDT started with fallback timeout ({MAX_WDT_TIMEOUT_MS}ms)")
                return wdt
            except Exception as e:
                error_log.log_exception(e, "init_wdt")
                return None
    except Exception as e:
        error_log.log_exception(e, "init_wdt")
        return None

def _handle_network_unavailable():
    """Handle WiFi disconnection and reconnection"""
    error_log.log_error("WIFI", "WiFi connection lost, reconnecting...")
    led_scheduler.start_pattern(LED_WIFI_CONNECTING)
    disconnect_mqtt()
    connect_wifi()
    if not connect_mqtt():
        error_log.log_error("MQTT", "Failed to reconnect after WiFi recovery")

def _run_main_loop():
    """Main event loop"""
    global last_message_time, consecutive_mqtt_errors, mqtt_reconnect_backoff, last_gc_time
    
    last_reconnect_attempt = time()
    mqtt_reconnect_backoff = MQTT_RECONNECT_BACKOFF_INIT

    while True:
        try:
            current_time = time()
            led_scheduler.update()

            if not is_network_available():
                _handle_network_unavailable()
                continue

            manage_memory(current_time)

            try:
                _process_mqtt_cycle(current_time)
            except OSError as e:
                consecutive_mqtt_errors += 1
                error_log.log_error("MQTT_ERROR", "OSError count", str(consecutive_mqtt_errors))
                if consecutive_mqtt_errors >= MQTT_ERROR_THRESHOLD:
                    error_log.log_error("MQTT", "Too many errors, forcing reconnect")
                    disconnect_mqtt()
                    gc.collect()
                    consecutive_mqtt_errors = 0
                raise

            # Sleep 1 second while keeping LED scheduler active
            for _ in range(10):
                led_scheduler.update()
                sleep(0.1)
            gc.collect()  # Opportunistic GC after successful cycle

        except Exception as e:
            error_log.log_exception(e, "message_check")
            current_time = time()
            last_reconnect_attempt, mqtt_reconnect_backoff = _attempt_reconnect(
                current_time,
                last_reconnect_attempt,
                mqtt_reconnect_backoff,
            )
            gc.collect()  # GC after error to recover memory
            # Sleep with scheduler updates
            for _ in range(10):
                led_scheduler.update()
                sleep(0.1)

def _handle_led_pattern(pattern_name):
    """Attempt to display LED pattern with fallback"""
    try:
        led_scheduler.start_pattern(pattern_name)
        while True:
            led_scheduler.update()
            sleep(0.1)
    except Exception as sched_err:
        error_log.log_exception(sched_err, "led_scheduler_failure")
        error_log.log_error("CRITICAL", "LED scheduler failed; fallback LED")
        gc.collect()  # Free memory before fallback
        _handle_direct_led()

def _handle_direct_led():
    """Direct LED blink as fallback when scheduler fails"""
    try:
        while True:
            led.on()
            sleep(0.5)
            led.off()
            sleep(0.5)
    except Exception as led_err:
        error_log.log_exception(led_err, "led_direct_failure")
        # Give up - just hang
        while True:
            sleep(1)

def _handle_critical_error(e):
    """Handle critical errors during startup"""
    error_log.log_exception(e, "main")
    error_log.log_error("CRITICAL", "Entering error handler; LED blink")
    gc.collect()  # Aggressive cleanup before diagnostics
    memory_monitor.print_diagnostics()
    error_log.print_stats()
    _handle_led_pattern(LED_ERROR)


def _process_mqtt_cycle(current_time):
    global last_message_time, consecutive_mqtt_errors

    if manager is None or not manager.is_connected():
        raise OSError('MQTT client not connected')

    manager.check_msg()
    last_message_time = current_time
    consecutive_mqtt_errors = 0


def _attempt_reconnect(current_time, last_reconnect_attempt, backoff):
    if current_time - last_reconnect_attempt <= backoff:
        return last_reconnect_attempt, backoff

    error_log.log_error("MQTT", "Attempting to reconnect", str(backoff))
    if connect_mqtt():
        error_log.log_error("MQTT", "Reconnection successful")
        return current_time, MQTT_RECONNECT_BACKOFF_INIT

    last_reconnect_attempt = current_time
    backoff = min(backoff * 2, MQTT_RECONNECT_BACKOFF_MAX)
    jitter = get_jitter(3)
    backoff += jitter
    error_log.log_error(
        "MQTT",
        "Reconnection failed",
        str(backoff) + "s jitter " + str(jitter)
    )
    return last_reconnect_attempt, backoff


def main():
    global wdt
    
    try:
        led_scheduler.start_pattern(LED_BOOT)
        error_log.log_error("STARTUP", "Application starting")
        error_log.print_stats()
        memory_monitor.print_diagnostics()

        gc.enable()
        gc.collect()  # Initial cleanup

        connect_wifi()
        gc.collect()  # Cleanup after WiFi

        if not connect_mqtt():
            raise RuntimeError('Failed to connect to MQTT')

        gc.collect()  # Cleanup before main loop
        # Initialize hardware watchdog
        wdt = _init_watchdog()

        _run_main_loop()

    except Exception as e:
        _handle_critical_error(e)

if __name__ == '__main__':
    main()

    