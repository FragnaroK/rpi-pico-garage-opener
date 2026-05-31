import machine
from time import sleep, time
import network
from umqtt.simple import MQTTClient
import config
import gc
import random
from picozero import pico_led
from error_logger import error_log
from memory_monitor import memory_monitor
import mqtt_manager
import lib.ugit.ugit as ugit

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

# Memory management settings
GC_COLLECT_INTERVAL = 30
MESSAGE_BUFFER_MAX = 10
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
RECONNECT_INTERVAL = 30
message_history = []
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

def connect_wifi():
    try:
        pico_led.blink(on_time=1)
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.config(pm = 0xa11140)
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        max_wait = 30
        while max_wait > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            max_wait -= 1
            sleep(1)

        if wlan.status() != 3:
            error_log.log_error("WIFI", "Failed to connect to WiFi")
            pico_led.blink(on_time=3, wait=True, n=3)
            raise RuntimeError('Network connection failed')
        else:
            error_log.log_error("WIFI", "Successfully connected to WiFi")
            pico_led.blink(on_time=0.15, wait=True, n=3)
    except Exception as e:
        error_log.log_exception(e, "connect_wifi")
        raise

def trigger_garage_door():
    try:
        pico_led.on()
        trigger_pin.value(ACTIVE_LOW)
        sleep(PRESS_DURATION)
        trigger_pin.value(ACTIVE_HIGH)
        pico_led.off()
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
        # Initialize manager if needed
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

        # Try to connect via manager
        disconnect_mqtt()
        sleep(1)
        ok = manager.connect()
        if ok:
            client = manager.client
            consecutive_mqtt_errors = 0
        return ok
    except Exception as e:
        error_log.log_exception(e, "connect_mqtt")
        consecutive_mqtt_errors += 1
        return False

def on_message(topic, message):
    """Handle incoming MQTT messages"""
    global message_history
    
    try:
        # Keep message history bounded
        message_history.append({'topic': topic, 'msg': message, 'time': time()})
        if len(message_history) > MESSAGE_BUFFER_MAX:
            message_history.pop(0)
        
        error_log.log_error("MQTT", f"Message received on {topic}", f"payload: {message}")
        
        # Trigger command
        if topic == MQTT_TOPIC_BASE and message == b'TRIGGER':
            error_log.log_error("GARAGE", "Garage door trigger command received")
            trigger_garage_door()
        # OTA trigger (pico/garage/ota)
        elif topic == MQTT_TOPIC_OTA:
            error_log.log_error("OTA", "OTA trigger received via MQTT")
            try:
                # Require explicit payload 'UPDATE' to avoid accidental OTA
                if isinstance(message, bytes) and message.strip().upper() == b'UPDATE':
                    # publish status ack (best-effort)
                    try:
                        if manager and manager.is_connected():
                            manager.publish(MQTT_TOPIC_STATUS, b'OTA_STARTED')
                    except Exception:
                        pass

                    # Start OTA (this will reset device on success)
                    def _notify_complete():
                        try:
                            if manager and manager.is_connected():
                                manager.publish(MQTT_TOPIC_STATUS, b'OTA_COMPLETED')
                        except Exception:
                            pass

                    ugit.safe_pull_all(isconnected=True, reset_after=True, on_complete=_notify_complete)
                else:
                    error_log.log_error("OTA", "Ignored OTA request: wrong payload", f"payload: {message}")
            except Exception as e:
                error_log.log_exception(e, "mqtt_ota")
                try:
                    if manager and manager.is_connected():
                        manager.publish(MQTT_TOPIC_STATUS, b'OTA_FAILED')
                except Exception:
                    pass
        else:
            error_log.log_error("MQTT", "Unknown command received", f"topic: {topic}, msg: {message}")
    except Exception as e:
        error_log.log_exception(e, "on_message")

def is_network_available():
    """Check if WiFi is still connected"""
    try:
        wlan = network.WLAN(network.STA_IF)
        return wlan.isconnected()
    except:
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

def main():
    global client, last_message_time, last_gc_time, consecutive_mqtt_errors, mqtt_reconnect_backoff
    global wdt
    
    try:
        error_log.log_error("STARTUP", "Application starting")
        error_log.print_stats()
        memory_monitor.print_diagnostics()
        
        gc.enable()
        
        connect_wifi()
        
        if not connect_mqtt():
            raise RuntimeError('Failed to connect to MQTT')

        # Initialize hardware watchdog to help recover from hangs
        try:
            wdt_timeout = WATCHDOG_TIMEOUT_MS
            if WATCHDOG_TIMEOUT_MS > MAX_WDT_TIMEOUT_MS:
                error_log.log_error("WATCHDOG", f"Requested WDT timeout {WATCHDOG_TIMEOUT_MS}ms exceeds max {MAX_WDT_TIMEOUT_MS}ms; clamping to {MAX_WDT_TIMEOUT_MS}ms")
                wdt_timeout = MAX_WDT_TIMEOUT_MS

            try:
                wdt = machine.WDT(timeout=wdt_timeout)
                error_log.log_error("WATCHDOG", f"WDT started ({wdt_timeout}ms)")
            except ValueError:
                # Some ports raise ValueError for too-large timeouts; try a safe fallback
                try:
                    wdt = machine.WDT(timeout=MAX_WDT_TIMEOUT_MS)
                    error_log.log_error("WATCHDOG", f"WDT started with fallback timeout ({MAX_WDT_TIMEOUT_MS}ms)")
                except Exception as e:
                    error_log.log_exception(e, "init_wdt")
                    wdt = None
        except Exception as e:
            error_log.log_exception(e, "init_wdt")
        
        last_reconnect_attempt = time()
        last_gc_time = time()
        mqtt_reconnect_backoff = MQTT_RECONNECT_BACKOFF_INIT
        
        # Main loop
        while True:
            try:
                current_time = time()
                
                # Check WiFi connectivity
                if not is_network_available():
                    error_log.log_error("WIFI", "WiFi connection lost, reconnecting...")
                    disconnect_mqtt()
                    connect_wifi()
                    if not connect_mqtt():
                        error_log.log_error("MQTT", "Failed to reconnect after WiFi recovery")
                    continue
                
                # Memory management
                manage_memory(current_time)
                
                # Check for incoming messages
                try:
                    if manager is None or not manager.is_connected():
                        raise OSError(-1)  # Force reconnect if client is None

                    manager.check_msg()
                    last_message_time = current_time
                    consecutive_mqtt_errors = 0
                except OSError as e:
                    consecutive_mqtt_errors += 1
                    error_log.log_error("MQTT_ERROR", f"OSError (count: {consecutive_mqtt_errors})", str(e))
                    
                    # Force reconnect after threshold
                    if consecutive_mqtt_errors >= MQTT_ERROR_THRESHOLD:
                        error_log.log_error("MQTT", "Too many errors, forcing reconnect")
                        disconnect_mqtt()
                        consecutive_mqtt_errors = 0
                    
                    raise  # Re-raise to handle in outer except
                
                # Quick blink to show we're alive
                pico_led.on()
                sleep(0.1)
                pico_led.off()
                sleep(0.9)
                
            except Exception as e:
                error_log.log_exception(e, "message_check")
                current_time = time()
                
                # Try to reconnect with exponential backoff
                if current_time - last_reconnect_attempt > mqtt_reconnect_backoff:
                    error_log.log_error("MQTT", f"Attempting to reconnect (backoff: {mqtt_reconnect_backoff}s)")
                    if connect_mqtt():
                        last_reconnect_attempt = current_time
                        mqtt_reconnect_backoff = MQTT_RECONNECT_BACKOFF_INIT
                        error_log.log_error("MQTT", "Reconnection successful")
                    else:
                        last_reconnect_attempt = current_time
                        # exponential backoff plus small jitter to avoid thundering herds
                        mqtt_reconnect_backoff = min(mqtt_reconnect_backoff * 2, MQTT_RECONNECT_BACKOFF_MAX)
                        jitter = get_jitter(3)
                        mqtt_reconnect_backoff = mqtt_reconnect_backoff + jitter
                        error_log.log_error("MQTT", f"Reconnection failed, next attempt in {mqtt_reconnect_backoff}s (jitter {jitter}s)")
                
                sleep(1)
                
    except Exception as e:
        error_log.log_exception(e, "main")
        memory_monitor.print_diagnostics()
        error_log.print_stats()
        pico_led.blink(on_time=0.5, wait=True, n=10)

if __name__ == '__main__':
    main()

    