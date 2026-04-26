from __future__ import annotations

import logging
from dataclasses import dataclass

import paho.mqtt.client as mqtt

from mtrview.config import Settings
from mtrview.store import SummaryStore

LOGGER = logging.getLogger(__name__)


@dataclass
class MqttStatus:
    connected: bool = False
    error: str | None = None


class MqttSubscriber:
    def __init__(self, settings: Settings, store: SummaryStore) -> None:
        self._settings = settings
        self._store = store
        self.status = MqttStatus()
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
        )
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        LOGGER.info(
            "Connecting to MQTT broker %s:%s and subscribing to %s",
            self._settings.mqtt_host,
            self._settings.mqtt_port,
            ", ".join(self._settings.mqtt_topics),
        )
        self._client.connect_async(
            self._settings.mqtt_host,
            self._settings.mqtt_port,
            self._settings.mqtt_keepalive,
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client: mqtt.Client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code == 0:
            self.status = MqttStatus(connected=True)
            for topic in self._settings.mqtt_topics:
                client.subscribe(topic)
            LOGGER.info("Connected to MQTT broker")
            return
        self.status = MqttStatus(connected=False, error=str(reason_code))
        LOGGER.error("MQTT connection failed: %s", reason_code)

    def _on_disconnect(
        self, _client: mqtt.Client, _userdata, _flags, reason_code, _properties
    ) -> None:
        self.status = MqttStatus(connected=False, error=str(reason_code))
        LOGGER.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(self, _client: mqtt.Client, _userdata, message: mqtt.MQTTMessage) -> None:
        receiver_hint = _receiver_from_topic(message.topic)
        self._store.update_from_json(receiver_hint, message.payload)


def _receiver_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) >= 2 and parts[0] == "summary":
        return parts[1]
    return topic
