import machine
from time import sleep, time
import network
from umqtt.simple import MQTTClient
import config
import gc
from picozero import pico_led
from error_logger import error_log
from memory_monitor import memory_monitor

# --- Constants for MQTT Topics
MQTT_TOPIC_GARAGE = b'pico/garage'

# --- MQTT Parameters
MQTT_SERVER = config.MQTT_SERVER
MQTT_PORT = 1883
MQTT_USER = config.MQTT_USERNAME
MQTT_PASSWORD = config.MQTT_PASSWORD
MQTT_CLIENT_ID = b"raspberrypi_picow"
MQTT_KEEPALIVE = 60
MQTT_SSL = False
MQTT_SSL_PARAMS = {'server_hostname': MQTT_SERVER}

# --- Constants
RELAY_PIN = const(16)
PRESS_DURATION = const(0.5)
ACTIVE_LOW = const(0)
ACTIVE_HIGH = const(1)

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
last_message_time = time()
last_gc_time = time()
RECONNECT_INTERVAL = 30
message_history = []
consecutive_mqtt_errors = 0
mqtt_reconnect_backoff = MQTT_RECONNECT_BACKOFF_INIT

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
        if client:
            error_log.log_error("MQTT", "Disconnecting from MQTT broker")
            client.disconnect()  # This now calls gc.collect() internally
    except Exception as e:
        error_log.log_exception(e, "disconnect_mqtt")
    finally:
        client = None
        gc.collect()  # Extra GC to be safe

def connect_mqtt():
    global client, consecutive_mqtt_errors
    try:
        # Clean disconnect before reconnecting
        disconnect_mqtt()
        sleep(1)  # Wait for OS to reclaim socket resources
        
        error_log.log_error("MQTT", "Creating new MQTT client")
        client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_SERVER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=MQTT_KEEPALIVE,
            ssl=MQTT_SSL,
            ssl_params=MQTT_SSL_PARAMS
        )
        client.set_callback(on_message)
        
        error_log.log_error("MQTT", "Connecting to MQTT broker")
        client.connect()
        
        error_log.log_error("MQTT", "Subscribing to topics")
        client.subscribe(MQTT_TOPIC_GARAGE)
        
        error_log.log_error("MQTT", "Successfully connected to MQTT broker")
        consecutive_mqtt_errors = 0
        return True
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
        
        if topic == MQTT_TOPIC_GARAGE and message == b'TRIGGER':
            error_log.log_error("GARAGE", "Garage door trigger command received")
            trigger_garage_door()
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
    
    if current_time - last_gc_time > GC_COLLECT_INTERVAL:
        gc.collect()
        last_gc_time = current_time
        memory_monitor.force_gc()
    
    memory_monitor.check_memory(current_time)

def main():
    global client, last_message_time, last_gc_time, consecutive_mqtt_errors, mqtt_reconnect_backoff
    
    try:
        error_log.log_error("STARTUP", "Application starting")
        error_log.print_stats()
        memory_monitor.print_diagnostics()
        
        gc.enable()
        
        connect_wifi()
        
        if not connect_mqtt():
            raise RuntimeError('Failed to connect to MQTT')
        
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
                    if client is None:
                        raise OSError(-1)  # Force reconnect if client is None
                    
                    client.check_msg()
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
                        mqtt_reconnect_backoff = min(mqtt_reconnect_backoff * 2, MQTT_RECONNECT_BACKOFF_MAX)
                        error_log.log_error("MQTT", f"Reconnection failed, next attempt in {mqtt_reconnect_backoff}s")
                
                sleep(1)
                
    except Exception as e:
        error_log.log_exception(e, "main")
        memory_monitor.print_diagnostics()
        error_log.print_stats()
        pico_led.blink(on_time=0.5, wait=True, n=10)

if __name__ == '__main__':
    main()

    