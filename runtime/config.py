import os
import json

CONFIG_PATH = '/config.json'
ENV_PATH = '.env'
REQUIRED_KEYS = [
    'WIFI_SSID',
    'WIFI_PASSWORD',
    'MQTT_SERVER',
    'MQTT_USER',
    'MQTT_PASSWORD',
]


def _read_env_file(path):
    values = {}
    try:
        with open(path, 'r') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                    value = value[1:-1]
                values[key] = value
    except Exception:
        pass
    return values


def _read_json_file(path):
    try:
        with open(path, 'r') as f:
            return json.loads(f.read())
    except Exception:
        return {}


def _merge_config(json_config, env_config):
    merged = {}
    merged.update(json_config)
    for key, value in env_config.items():
        if value and key not in merged:
            merged[key] = value
    return merged


def load_config():
    json_config = _read_json_file(CONFIG_PATH)
    env_config = _read_env_file(ENV_PATH)
    return _merge_config(json_config, env_config)


def _normalize_repository(repo):
    if not repo:
        return ''
    s = repo.strip()
    if s.startswith('git@') and ':' in s:
        s = s.split(':', 1)[1]
    if s.startswith('http'):
        parts = s.split('/')
        if len(parts) >= 2:
            s = '/'.join(parts[-2:])
    if s.endswith('.git'):
        s = s[:-4]
    if '/' in s:
        return s.split('/')[-1]
    return s


def create_config(ssid='', password='', user='', repository='', branch='main', ignore=None):
    import lib.ugit as ugit

    if ignore is None:
        ignore = []

    ignore_list = list(ignore)
    for path in ['/ugit.py', '/config.json', '/ugit.backup', '/ugit_log.txt', '/lib', '/sd']:
        if path not in ignore_list:
            ignore_list.append(path)

    ugit.create_config(
        ssid=ssid,
        password=password,
        user=user,
        repository=repository,
        branch=branch,
        ignore=ignore_list,
    )


def validate_config(config):
    return [key for key in REQUIRED_KEYS if not config.get(key, '')]


_config = load_config()

WIFI_SSID = _config.get('WIFI_SSID', '')
WIFI_PASSWORD = _config.get('WIFI_PASSWORD', '')
MQTT_SERVER = _config.get('MQTT_SERVER', '')
MQTT_USER = _config.get('MQTT_USER', '').encode()
MQTT_PASSWORD = _config.get('MQTT_PASSWORD', '').encode()
GH_USER = _config.get('GH_USER', '')
GH_REPO = _config.get('GH_REPO', '')
GH_BRANCH = _config.get('GH_BRANCH', 'main')

if __name__ == '__main__':
    env_config = _read_env_file(ENV_PATH)
    missing = [
        key for key in ['WIFI_SSID', 'WIFI_PASSWORD', 'GH_USER', 'GH_REPO', 'GH_BRANCH', 'MQTT_SERVER', 'MQTT_USER', 'MQTT_PASSWORD']
        if not env_config.get(key, '')
    ]
    if missing:
        print('Warning: the following required env variables are empty or missing:', missing)

    repo_name = _normalize_repository(env_config.get('GH_REPO', ''))
    print('Will write config for user=%s, repository=%s, branch=%s' % (
        env_config.get('GH_USER', ''), repo_name, env_config.get('GH_BRANCH', 'main')
    ))

    create_config(
        ssid=env_config.get('WIFI_SSID', ''),
        password=env_config.get('WIFI_PASSWORD', ''),
        user=env_config.get('GH_USER', ''),
        repository=repo_name,
        branch=env_config.get('GH_BRANCH', 'main'),
    )
