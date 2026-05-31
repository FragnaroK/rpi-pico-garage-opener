# rpi-pico-garage-opener

Improvements and utilities for Raspberry Pi Pico W garage opener project.

What's included:
- `main.py` — application entry; now uses `mqtt_manager` and a hardware watchdog.
- `mqtt_manager.py` — small wrapper over `umqtt.simple.MQTTClient` for reconnect/LWT/status.
 - `lib/ugit/ugit.py` — OTA updater that pulls files from a GitHub repo and syncs them to the Pico filesystem.
 - `boot.py` — optional boot-time OTA trigger (hold GPIO0 low during boot to update).

Recommended next steps:
- Test on-device with a local MQTT broker (Mosquitto). For TLS enable `MQTT_SSL` and set `MQTT_SSL_PARAMS` appropriately in `config.py`.
- Tune `WATCHDOG_TIMEOUT_MS` in `main.py` to match your expected operation (default 15000 ms).

OTA usage
 - Create a GitHub repo containing the files you want the Pico to download (e.g., `main.py`).
 - Configure device settings via `config.py` / `.env` so `lib.dotenv` can load `WIFI_SSID`, `WIFI_PASSWORD`, `GH_USER`, `G_REPO`, `GH_BRANCH`.
 - Save `lib/ugit/ugit.py` to the device (already in this project). On first run `config.py` will call `ugit.create_config()` to persist settings.
 - To trigger OTA on boot: hold a pushbutton that ties GPIO0 to GND while powering the Pico; `boot.py` will call `ugit.safe_pull_all()`.

Notes
 - `ugit.safe_pull_all()` will attempt to delete local files not present in the GitHub tree (except files listed in `ignore` in the ugit config), but it performs pre-flight checks and creates a backup first. Use `ugit.backup()` before running updates if needed.
 - For private repos, supply a GitHub token via `.env` and the `create_config` call.

Testing (host):
There is a simple host-side test in `tests/test_mqtt_manager.py` that uses a mocked client. Run tests with Python 3 on your workstation.
