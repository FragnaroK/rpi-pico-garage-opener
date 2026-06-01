import time
import gc
from umqtt.simple import MQTTClient
from error_logger import error_log

DEFAULT_STATUS_SUFFIX = b'/status'
ERROR_NOT_CONNECTED = 'Not connected'


class MQTTManager:
    """Wrapper around umqtt.simple.MQTTClient with robust reconnect logic,
    Last Will, and status publishing.

    Features:
    - Automatic socket cleanup on failed operations
    - Socket sanity checks
    - Safe publish/subscribe with error recovery
    - Connection diagnostics
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
        self.connect_count = 0
        self.last_error = None

    def _verify_socket(self):
        """Sanity check: ensure socket exists and is usable."""
        if not self.client:
            return False
        try:
            sock = getattr(self.client, 'sock', None)
            return sock is not None
        except Exception:
            return False

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
            self.connect_count += 1
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
            self.last_error = None
            return True
        except Exception as e:
            self.last_error = str(e)
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

    def get_status(self):
        """Return a dict with current connection status for diagnostics."""
        return {
            'connected': self.is_connected(),
            'connect_count': self.connect_count,
            'last_error': self.last_error,
            'last_ping_age': time.time() - self.last_ping if self.last_ping else -1,
        }

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
        """Check for incoming MQTT messages; safe socket error recovery."""
        if not self._verify_socket():
            raise OSError(ERROR_NOT_CONNECTED)

        try:
            if hasattr(self.client, 'check_msg'):
                return self.client.check_msg()
            else:
                return self.client.wait_msg()
        except OSError as e:
            self.last_error = str(e)
            self.client = None
            raise
        finally:
            self._send_keepalive_ping()

    def is_connected(self):
        """Safe check: verify connection without throwing."""
        try:
            return self._verify_socket()
        except Exception:
            return False

    def subscribe_safe(self, topic):
        """Subscribe with error handling; returns success status."""
        if not self.is_connected():
            self.last_error = 'Not connected'
            return False
        try:
            self.client.subscribe(topic)
            return True
        except Exception as e:
            self.last_error = f'Subscribe failed: {str(e)}'
            return False

    def publish_safe(self, topic, msg, retain=False, qos=0):
        """Publish with error handling; returns success status."""
        if not self.is_connected():
            self.last_error = 'Not connected'
            return False
        try:
            self.client.publish(topic, msg, retain=retain, qos=qos)
            return True
        except Exception as e:
            self.last_error = f'Publish failed: {str(e)}'
            return False
