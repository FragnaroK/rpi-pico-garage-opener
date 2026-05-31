# This script should only be run once to generate config.json (should not be pushed to repo)

import lib.ugit.ugit as ugit
import lib.dotenv.dotenv as dotenv

# Load config
required_keys = ["WIFI_SSID", "WIFI_PASSWORD", "GH_USER", "GH_REPO", "GH_BRANCH", "MQTT_SERVER", "MQTT_USER", "MQTT_PASSWORD"]
config = dotenv.load(filepath='./.env')

WIFI_SSID=config.get("WIFI_SSID", "")
WIFI_PASSWORD=config.get("WIFI_PASSWORD", "")

GH_USER=config.get("GH_USER", "")
GH_REPO=config.get("GH_REPO", "")
GH_BRANCH=config.get("GH_BRANCH", "")

MQTT_SERVER=config.get("MQTT_SERVER", "")
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

def _normalize_repository(repo):
    """Normalize repository input into a bare repository name.

    Accepts values like:
      - rpi-pico-garage-opener
      - FragnaroK/rpi-pico-garage-opener
      - git@github.com:FragnaroK/rpi-pico-garage-opener.git
      - https://github.com/FragnaroK/rpi-pico-garage-opener.git

    Returns the repo name portion: "rpi-pico-garage-opener".
    """
    if not repo:
        return ''
    s = repo.strip()
    # SSH form: git@github.com:owner/repo.git
    if s.startswith('git@') and ':' in s:
        s = s.split(':', 1)[1]
    # HTTP(S) form: https://github.com/owner/repo(.git)
    if s.startswith('http'):
        # drop protocol and domain
        parts = s.split('/')
        if len(parts) >= 2:
            # last two parts are owner and repo
            s = '/'.join(parts[-2:])
    # strip trailing .git
    if s.endswith('.git'):
        s = s[:-4]
    # if owner/repo, return repo part
    if '/' in s:
        return s.split('/')[-1]
    return s


repo_name = _normalize_repository(GH_REPO)

print('Will write config for user=%s, repository=%s, branch=%s' % (GH_USER, repo_name, GH_BRANCH))

ugit.create_config(
    ssid=WIFI_SSID,
    password=WIFI_PASSWORD,
    user=GH_USER,
    repository=repo_name,
    branch=GH_BRANCH,
    ignore=ignore_files
)
