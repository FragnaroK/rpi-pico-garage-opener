import time
import gc
from umqtt.simple import MQTTClient
from error_logger import error_log

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
        self.server = server.decode('utf-8') if isinstance(server, bytes) else server
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
        error_log.log_error("MQTT", "Attempting MQTT connect", f"server={self.server} user={self.user}")
        # Tear down any existing client if stale or broken
        try:
            if self.client:
                error_log.log_error("MQTT", "Disconnecting stale existing MQTT client before reconnect")
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
        except Exception as e:
            error_log.log_error("MQTT", "connect failed", str(e))
            self.client = None
            return False

    def disconnect(self):
        try:
            if self.client:
                error_log.log_error("MQTT", "Client disconnect requested")
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

        # Prefer non-blocking check_msg if available, otherwise fallback
        # to wait_msg inside a safe try/except.
        try:
            if hasattr(self.client, 'check_msg'):
                return self.client.check_msg()
            else:
                return self.client.wait_msg()
        finally:
            self._send_keepalive_ping()

    def is_connected(self):
        try:
            return self.client is not None and getattr(self.client, 'sock', None) is not None
        except Exception:
            return False
