from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from nagabridge.core.adapter import Adapter
from nagabridge.core.health import HealthStatus
from nagabridge.core.bus import EventBus, Payload, Topic


@dataclass(slots=True)
class MqttAdapterConfig:
    host: str
    port: int = 1883
    user: str | None = None
    password: str | None = None
    subscribe_topics: list[str] = field(
        default_factory=lambda: ["ecoflow/powerstream/state"]
    )
    publish_prefix: str = "nagabridge"


class MqttAdapter(Adapter):
    def __init__(
        self,
        config: MqttAdapterConfig,
        client_factory: Any | None = None,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._health = HealthStatus(False, "not started")
        self._bus: EventBus | None = None
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return "mqtt"

    @property
    def version(self) -> str:
        return "0.3.0"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        self._bus = bus
        if self._client_factory is None:
            try:
                import paho.mqtt.client as mqtt_client
            except ModuleNotFoundError as exc:
                raise RuntimeError("paho-mqtt is required for MqttAdapter") from exc
            self._client = mqtt_client.Client()
        else:
            self._client = self._client_factory()

        if self._config.user:
            self._client.username_pw_set(self._config.user, self._config.password)

        self._client.connect(self._config.host, self._config.port)
        self._client.loop_start()

        for topic in self._config.subscribe_topics:
            await bus.subscribe(topic, self._on_bus_event)

        self._health = HealthStatus(
            True, f"connected to {self._config.host}:{self._config.port}"
        )

    async def stop(self) -> None:
        if self._bus is not None:
            for topic in self._config.subscribe_topics:
                await self._bus.unsubscribe(topic, self._on_bus_event)

        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()

        self._health = HealthStatus(False, "stopped")
        self._client = None
        self._bus = None

    async def _on_bus_event(self, topic: Topic, payload: Payload) -> None:
        if self._client is None:
            return

        mqtt_topic = self._map_topic(topic)
        self._client.publish(mqtt_topic, json.dumps(payload), qos=0, retain=False)

    def _map_topic(self, topic: Topic) -> str:
        return f"{self._config.publish_prefix}/{topic}"
