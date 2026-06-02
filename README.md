# Raspberry Pi Pico W Garage Door Opener

A MicroPython-based remote garage door control system for the Raspberry Pi Pico W. Features WiFi/MQTT control, over-the-air (OTA) updates via GitHub, LED status indicators, and robust memory management.

## Hardware Requirements

- Raspberry Pi Pico W
- Relay module (to trigger garage door opener)
- Built-in LED (GPIO 25 on Pico W)
- WiFi network
- MQTT broker (e.g., Home Assistant, Mosquitto)

### Wiring

| Pico Pin | Component | Purpose |
|----------|-----------|---------|
| GPIO 21 | Relay IN | Garage door trigger signal |
| GPIO 25 | Built-in LED | Status indicator |

## File Structure

```
.
├── boot.py                    # Minimal startup initialization
├── main.py                    # Main application runtime
├── runtime/                   # Runtime modules
│   ├── __init__.py            # runtime package initializer
│   ├── config.py              # Runtime config loader (reads /config.json or .env)
│   ├── error_logger.py        # Circular log buffer with file persistence
│   ├── memory_monitor.py      # Memory usage tracking and auto-reboot
│   ├── mqtt_manager.py        # MQTT client wrapper with robust reconnect
│   └── led_scheduler.py       # Non-blocking LED pattern manager
├── tools/                     # Utility scripts
│   ├── dev/                   # Development utilities (run on workstation or Thonny)
│   │   ├── config_generator.py # One-time config generator from .env
│   │   ├── test_led.py        # LED diagnostic runner
│   │   └── setup_config.py    # Interactive config helper
│   └── runtime/               # Runtime helpers (device-side tools)
├── lib/
│   ├── led.py                 # LED control and patterns
│   ├── dotenv/                # Dotenv parser
│   └── ugit/                  # Over-the-air update support
└── .env                       # Device credentials (local only, not pushed)
```

## First-Time Setup

### 1. Prepare `.env` File

Create a `.env` file **locally** (on your Pico) with your credentials:

```
WIFI_SSID=your_wifi_name
WIFI_PASSWORD=your_wifi_password
GH_USER=your_github_username
GH_REPO=rpi-pico-garage-opener
GH_BRANCH=main
MQTT_SERVER=192.168.1.100
MQTT_USER=mqtt_user
MQTT_PASSWORD=mqtt_password
```

**Never push `.env` to GitHub.** The `.gitignore` excludes it automatically.

### 2. Generate Device Config

Run the config generator **once** on the Pico to create `/config.json`:

#### Option A: Using Thonny

1. Open `tools/dev/config_generator.py` in Thonny
2. Ensure `.env` is on the Pico (via file transfer)
3. Run the script
4. Check the output and confirm `/config.json` was created

#### Option B: Using REPL

```python
import runtime.config as config
config.create_config(
    ssid='your_wifi_name',
    password='your_wifi_password',
    user='your_github_username',
    repository='rpi-pico-garage-opener',
    branch='main'
)
```

### 3. Power On and Boot

- Reset the Pico or power it on
- Observe **LED boot pattern** (two quick flashes)
- Watch for **WiFi connecting** pattern (steady 1s blink)
- Once connected, **WiFi connected** pattern (two short pulses)
- MQTT will auto-connect; **MQTT connected** pattern (single pulse)

## LED Status Indicators

| Pattern | Meaning | Duration |
|---------|---------|----------|
| Two fast pulses | Boot in progress | ~2 seconds |
| Steady 1s blink | WiFi connecting | Until connected |
| Two short pulses | WiFi connected | ~1 second, then off |
| Single pulse | MQTT connected | ~0.5 seconds, then off |
| Rapid triple blink | MQTT error / retry | ~1.8 seconds |
| Fast on-off | OTA update in progress | Until complete |
| Slow blink | Fatal error | Continuous |

## MQTT Topics

| Topic | Payload | Purpose |
|-------|---------|---------|
| `pico/garage` | `TRIGGER` | Trigger garage door (press relay) |
| `pico/garage/status` | `ONLINE` / `OFFLINE` | Device status (retained) |
| `pico/garage/ota` | `UPDATE` | Trigger OTA update |

### Example: Trigger Garage Door

**Using MQTT CLI:**

```bash
mosquitto_pub -h 192.168.1.100 -u mqtt_user -P mqtt_password \
  -t pico/garage -m TRIGGER
```

**Using Home Assistant:**

Add to `configuration.yaml`:

```yaml
mqtt:
  broker: 192.168.1.100

button:
  - platform: mqtt
    name: "Garage Door"
    command_topic: "pico/garage"
    payload_press: "TRIGGER"
```

## Over-the-Air (OTA) Updates

The device can pull and install updates directly from your GitHub repository using `ugit`.

### Enable OTA

1. Push your changes to your GitHub fork (e.g., `branch: main`)
2. Send OTA trigger via MQTT:

```bash
mosquitto_pub -h 192.168.1.100 -u mqtt_user -P mqtt_password \
  -t pico/garage/ota -m UPDATE
```

### What Happens During OTA

1. LED switches to **fast blink** (OTA pattern)
2. Device fetches latest code from GitHub
3. Files are updated (except `/config.json` and `/ugit.py`, which are protected)
4. Device reboots and loads new code
5. LED returns to normal patterns

### Files Protected from Sync

- `/config.json` (your device credentials)
- `/ugit.py` (OTA updater itself)
- `/lib/ugit/` (OTA library)
- `/.env` (if present)

## Memory Management

The device monitors heap usage and takes action at thresholds:

- **80%**: Warning logged; garbage collection forced
- **85%**: Critical; device auto-reboots to prevent crashes

Check memory stats by reading `error_log.txt`:

```bash
# On device, via REPL:
from error_logger import error_log
error_log.print_stats()
```

## Troubleshooting

### Device Doesn't Connect to WiFi

1. Check LED patterns (should see steady blink if connecting)
2. Verify SSID/password in `.env` or via `runtime.config.py`
3. Check WiFi signal strength at the device location
4. Inspect `error_log.txt` for WiFi errors

### MQTT Connection Fails

1. Check MQTT broker is running at the configured IP/port
2. Verify username/password in config
3. Test connectivity: `mosquitto_pub -h <server> -u <user> -P <pass> -t test -m hello`
4. Check firewall rules (MQTT default port is 1883)

### OTA Update Doesn't Work

1. Verify GitHub repo URL and branch in config
2. Check internet/WiFi connectivity during OTA
3. Ensure write permissions on `/` (MicroPython filesystem)
4. Watch LED for OTA pattern; if it stops, check logs

### Infinite Reboot Loop

1. Device likely hit memory critical threshold (85%)
2. Try booting with minimal MQTT activity (unplugging relay control temporarily)
3. Check `error_logger.py` thresholds and adjust if needed

## Logs and Diagnostics

### Error Log File

Saved to `error_log.txt` on the device (max ~50 KB):

```bash
# Read from REPL:
with open('error_log.txt', 'r') as f:
    print(f.read())
```

### Check Status via REPL

```python
# Memory usage
from memory_monitor import memory_monitor
memory_monitor.print_diagnostics()

# MQTT connection status
from main import manager
print(manager.get_status())

# Error log stats
from error_logger import error_log
error_log.print_stats()
```

## Development & Customization

### Changing LED Patterns

Edit `lib/led.py` or `led_scheduler.py` to add custom patterns.

### Adjusting Memory Thresholds

In `memory_monitor.py`:

```python
memory_monitor = MemoryMonitor(
    check_interval=60,          # Check every 60 seconds
    warning_threshold=80,       # Warn at 80%
    reboot_threshold=85,        # Reboot at 85%
    log_interval=300            # Log stats every 5 minutes
)
```

### Custom MQTT Commands

Add handlers in `on_message()` in `main.py` for additional topics.

## Security Notes

- `.env` and `/config.json` contain passwords; keep them private
- Never commit `.env` to GitHub (`.gitignore` already excludes it)
- Use strong MQTT credentials on your broker
- WiFi password is stored unencrypted on the device (Pico W has no secure storage)

## Performance Tips

- WiFi PM mode is disabled (`pm=0xa11140`) for reliable connectivity
- Garbage collection runs every 30 seconds by default
- MQTT keepalive pings every 30 seconds
- LED scheduler updates every 100ms for smooth patterns
- Main loop runs at ~1 Hz (1 second cycle)

## References

- [MicroPython Docs](https://docs.micropython.org/)
- [Raspberry Pi Pico W](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
- [ugit OTA Updates](https://github.com/turfptax/ugit)
- [umqtt Library](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)

## License

This project is open-source. See `LICENSE` or your project repository for details.
