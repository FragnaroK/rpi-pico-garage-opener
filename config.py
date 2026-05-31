# This script should only be run once to generate config.json (should not be pushed to repo)

import lib.ugit.ugit as ugit
import lib.dotenv.dotenv as dotenv

# Load config
required_keys = ["WIFI_SSID", "WIFI_PASSWORD", "GH_USER", "GH_REPO", "GH_BRANCH", "MQTT_SERVER", "MQTT_USER", "MQTT_PASSWORD"]
config = dotenv.load(filepath='./.env')

WIFI_SSID=config.get("WIFI_SSID", "")
WIFI_PASSWORD=config.get("WIFI_PASSWORD", "")

GH_USER=config.get("GH_USER", "")
G_REPO=config.get("G_REPO", "")
GH_BRANCH=config.get("GH_BRANCH", "")
# GH_TOKEN=config.get("GH_TOKEN")

MQTT_SERVER=config.get("MQTT_SERVER", "").encode()
MQTT_USER=config.get("MQTT_USER", "").encode()
MQTT_PASSWORD=config.get("MQTT_PASSWORD", "").encode()

# Validate env config
missing_vars = [
    key for key in required_keys
    if not config.get(key, "")
]

if missing_vars:
    print('Warning: the following required env variables are empty or missing:', missing_vars)


ignore_files=["/lib/ugit/ugit.py", "/.env"]

ugit.create_config(
    ssid=WIFI_SSID,
    password=WIFI_PASSWORD,
    user=GH_USER,
    repository=G_REPO,
    branch=GH_BRANCH,
    ignore=ignore_files
    # token=GH_TOKEN  # optional: GitHub personal access token for private repos
)