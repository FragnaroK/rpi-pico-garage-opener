import unittest

import mqtt_manager


class DummyClient:
    def __init__(self):
        self.connected = False

    def set_last_will(self, topic, msg, retain=False):
        pass

    def set_callback(self, cb):
        pass

    def connect(self):
        self.connected = True

    def subscribe(self, topic):
        pass

    def publish(self, topic, msg, retain=False):
        return True

    def disconnect(self):
        self.connected = False

    def check_msg(self):
        return None


class MQTTManagerTest(unittest.TestCase):
    def test_connect_disconnect(self):
        mgr = mqtt_manager.MQTTManager(client_id=b'test', server='127.0.0.1')
        # Monkeypatch underlying MQTTClient with dummy
        mgr.client = DummyClient()
        self.assertFalse(mgr.is_connected() == False or mgr.client is not None)

    def test_publish_without_connect(self):
        mgr = mqtt_manager.MQTTManager(client_id=b'test', server='127.0.0.1')
        with self.assertRaises(OSError):
            mgr.publish(b'topic', b'msg')


if __name__ == '__main__':
    unittest.main()
