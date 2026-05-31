import time
import gc
from umqtt.simple import MQTTClient

DEFAULT_STATUS_SUFFIX = b'/status'
ERROR_NOT_CONNECTED = 'Not connected'


class MQTTManager:
    """Small wrapper around umqtt.simple.MQTTClient to centralize reconnect
    logic, Last Will, and status publishing.
    """
    def __init__(self, client_id, server, port=1883, user=None, password=None,
                 keepalive=60, ssl=False, ssl_params=None,
                 topic_base=b'pico/garage', lw_topic=None, lw_msg=b'OFFLINE'):
        self.client_id = client_id
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.ssl = ssl
        self.ssl_params = ssl_params or {}
        self.topic_base = topic_base
        self.lw_topic = lw_topic or (topic_base + DEFAULT_STATUS_SUFFIX)
        self.lw_msg = lw_msg

        self.client = None
        self.cb = None
        self.last_ping = 0

    def set_callback(self, cb):
        self.cb = cb

    def connect(self):
        # Tear down any existing client
        try:
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                self.client = None
                gc.collect()

            self.client = MQTTClient(
                client_id=self.client_id,
                server=self.server,
                port=self.port,
                user=self.user,
                password=self.password,
                keepalive=self.keepalive,
                ssl=self.ssl,
                ssl_params=self.ssl_params,
            )
            # set last will
            try:
                self.client.set_last_will(self.lw_topic, self.lw_msg, retain=True)
            except Exception:
                pass

            if self.cb:
                self.client.set_callback(self.cb)

            self.client.connect()
            # subscribe to base topic for commands and OTA trigger
            self.client.subscribe(self.topic_base)
            try:
                self.client.subscribe(self.topic_base + b'/ota')
            except Exception:
                pass
            # publish online status
            try:
                self.client.publish(self.topic_base + DEFAULT_STATUS_SUFFIX, b'ONLINE', retain=True)
            except Exception:
                pass
            self.last_ping = time.time()
            return True
        except Exception:
            return False

    def disconnect(self):
        try:
            if self.client:
                try:
                    self.client.publish(self.topic_base + DEFAULT_STATUS_SUFFIX, b'OFFLINE', retain=True)
                except Exception:
                    pass
                try:
                    self.client.disconnect()
                except Exception:
                    pass
        finally:
            self.client = None
            self.last_ping = 0
            gc.collect()

    def publish(self, topic, msg, retain=False, qos=0):
        if not self.client:
            raise OSError('Not connected')
        return self.client.publish(topic, msg, retain=retain, qos=qos)

    def _send_keepalive_ping(self):
        if not self.keepalive or not self.client:
            return
        now = time.time()
        if now - self.last_ping >= self.keepalive / 2:
            self.client.ping()
            self.last_ping = now

    def check_msg(self):
        if not self.client or not getattr(self.client, 'sock', None):
            raise OSError(ERROR_NOT_CONNECTED)
        sock = self.client.sock
        if sock is None:
            raise OSError(ERROR_NOT_CONNECTED)
        sock.setblocking(False)
        try:
            result = self.client.wait_msg()
            return result
        finally:
            self._send_keepalive_ping()

    def is_connected(self):
        return self.client is not None and getattr(self.client, 'sock', None) is not None
