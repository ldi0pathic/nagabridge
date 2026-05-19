"""Topic helpers shared across adapters (ADR-002, ADR-011)."""

from __future__ import annotations


def normalize_entity(name: str) -> str:
    """Normalize a device name to a topic entity segment."""
    return name.strip().lower().replace(" ", "_")


def state_topic(domain: str, name: str) -> str:
    return f"{domain}/{normalize_entity(name)}/state"


def command_topic(domain: str, name: str) -> str:
    return f"{domain}/{normalize_entity(name)}/command"


def bat_state_topic(domain: str, name: str) -> str:
    return f"{domain}/{normalize_entity(name)}_battery/state"
