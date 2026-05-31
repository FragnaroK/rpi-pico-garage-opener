import time
import gc
from umqtt.simple import MQTTClient


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
        self.lw_topic = lw_topic or (topic_base + b'/status')
        self.lw_msg = lw_msg

        self.client = None
        self.cb = None

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
                self.client.publish(self.topic_base + b'/status', b'ONLINE', retain=True)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def disconnect(self):
        try:
            if self.client:
                try:
                    self.client.publish(self.topic_base + b'/status', b'OFFLINE', retain=True)
                except Exception:
                    pass
                try:
                    self.client.disconnect()
                except Exception:
                    pass
        finally:
            self.client = None
            gc.collect()

    def publish(self, topic, msg, retain=False, qos=0):
        if not self.client:
            raise OSError('Not connected')
        return self.client.publish(topic, msg, retain=retain, qos=qos)

    def check_msg(self):
        if not self.client:
            raise OSError('Not connected')
        return self.client.check_msg()

    def is_connected(self):
        return self.client is not None
