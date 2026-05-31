from lib.ugit import ugit
from machine import Pin

# On-boot OTA trigger: hold GPIO0 to start pull_all()
try:
    pin = Pin(0, Pin.IN, Pin.PULL_UP)
    if pin.value() == 0:
        try:
            ugit.safe_pull_all(reset_after=True)
        except Exception as e:
            # best-effort: log to ugit_log
            try:
                with open('ugit_error.log', 'w') as f:
                    f.write(str(e))
            except Exception:
                pass
except Exception:
    # If machine.Pin not available (running on host), ignore
    pass
