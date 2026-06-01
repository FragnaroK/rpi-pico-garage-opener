import lib.ugit.ugit as ugit

REQUIRED_KEYS = [
    "WIFI_SSID",
    "WIFI_PASSWORD",
    "GH_USER",
    "GH_REPO",
    "GH_BRANCH",
    "MQTT_SERVER",
    "MQTT_USER",
    "MQTT_PASSWORD",
]

IGNORE_FILES = ["/lib/ugit/ugit.py", "/.env"]


def _load_env(filepath='.env'):
    config = {}
    try:
        with open(filepath, 'r') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                value = value.strip()
                if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                    value = value[1:-1]
                config[key.strip()] = value
    except Exception:
        pass
    return config


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


def _validate_config(config):
    return [key for key in REQUIRED_KEYS if not config.get(key, '')]


def main():
    config = _load_env('.env')
    missing = _validate_config(config)
    if missing:
        print('Warning: the following required env variables are empty or missing:', missing)

    wifi_ssid = config.get('WIFI_SSID', '')
    wifi_password = config.get('WIFI_PASSWORD', '')
    gh_user = config.get('GH_USER', '')
    gh_repo = _normalize_repository(config.get('GH_REPO', ''))
    gh_branch = config.get('GH_BRANCH', 'main')

    print('Will write config for user=%s, repository=%s, branch=%s' % (gh_user, gh_repo, gh_branch))

    ugit.create_config(
        ssid=wifi_ssid,
        password=wifi_password,
        user=gh_user,
        repository=gh_repo,
        branch=gh_branch,
        ignore=IGNORE_FILES,
    )


if __name__ == '__main__':
    main()
