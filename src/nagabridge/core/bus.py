# =============================================================================
# core/bus.py - Event Bus
#
# Zentraler Kommunikationskanal zwischen allen Adaptern.
# Kein Adapter kennt einen anderen – alle kommunizieren nur über den Bus.
#
# Prinzipien (siehe ADR-001, ADR-002, ADR-003):
#   - Fire-and-forget, kein Buffering, keine Backpressure
#   - State-First: nur der aktuellste Wert zählt
#   - Bus ist zustandslos: keine Commands, keine States gespeichert
#   - Topics: <domain>/<entity>/<type>
# =============================================================================

import asyncio
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

log = logging.getLogger("nagabridge.bus")

# Typ-Aliase
Topic = str
Payload = dict[str, Any]
Handler = Callable[[Topic, Payload], Coroutine[Any, Any, None]]
TOPIC_PATTERN = re.compile(r"^[^/]+/[^/]+/[^/]+$")


class EventBus:
    """
    Asyncio-basierter Event Bus.

    Jeder Adapter subscribt auf Topics und publisht Payloads.
    Der Bus verteilt eingehende Events direkt an alle Subscriber –
    ohne Queue, ohne Blockierung.

    Verwendung:
        bus = EventBus()

        # Subscriber registrieren
        await bus.subscribe("ecoflow/powerstream/state", my_handler)

        # Event publishen
        await bus.publish("ecoflow/powerstream/state", {"power": 120})

        # Subscriber entfernen
        await bus.unsubscribe("ecoflow/powerstream/state", my_handler)
    """

    def __init__(self):
        # topic → Liste von Handlern
        self._subscribers: dict[Topic, list[Handler]] = {}

    async def subscribe(self, topic: Topic, handler: Handler) -> None:
        """Registriert einen Handler für ein Topic."""
        self._validate_topic(topic)
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
            log.debug("subscribe: %s → %s", topic, handler.__qualname__)

    async def unsubscribe(self, topic: Topic, handler: Handler) -> None:
        """Entfernt einen Handler von einem Topic."""
        self._validate_topic(topic)
        if topic in self._subscribers:
            if handler in self._subscribers[topic]:
                self._subscribers[topic].remove(handler)
            log.debug("unsubscribe: %s → %s", topic, handler.__qualname__)

    async def publish(self, topic: Topic, payload: Payload) -> None:
        """
        Verteilt ein Event an alle Subscriber des Topics.

        Fire-and-forget: langsame Subscriber können Events verlieren.
        Das ist für State-Daten akzeptiert (ADR-003).
        Jeder Handler wird als eigener Task gestartet – kein Handler
        kann den Bus blockieren.
        """
        self._validate_topic(topic)
        handlers = self._subscribers.get(topic, [])

        if not handlers:
            log.debug("publish (no subscribers): %s", topic)
            return

        log.debug("publish: %s → %d subscriber(s)", topic, len(handlers))

        for handler in handlers:
            asyncio.create_task(self._call_handler(handler, topic, payload))

    async def _call_handler(
        self, handler: Handler, topic: Topic, payload: Payload
    ) -> None:
        """Ruft einen Handler auf und fängt Exceptions ab."""
        try:
            await handler(topic, payload)
        except Exception:
            log.exception(
                "Handler-Fehler: %s auf topic '%s'",
                handler.__qualname__,
                topic,
            )

    def subscriber_count(self, topic: Topic) -> int:
        """Gibt die Anzahl der Subscriber für ein Topic zurück."""
        self._validate_topic(topic)
        return len(self._subscribers.get(topic, []))

    def _validate_topic(self, topic: Topic) -> None:
        """Validiert Topics nach dem Schema <domain>/<entity>/<type>."""
        if not TOPIC_PATTERN.match(topic):
            raise ValueError(
                f"Ungültiges Topic '{topic}'. Erwartet: <domain>/<entity>/<type>."
            )

    @property
    def topics(self) -> list[Topic]:
        """Gibt alle Topics mit mindestens einem Subscriber zurück."""
        return [t for t, h in self._subscribers.items() if h]
