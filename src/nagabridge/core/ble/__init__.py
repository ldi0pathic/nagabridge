"""Reusable BLE connection abstractions."""

from .client import BleakClientAdapter, BleClient
from .connection import BleConnection, BleConnectionConfig, ClientFactory, NotificationHandler
from .exceptions import BleConnectionError, BleError, BleOperationError

__all__ = [
    "BleClient",
    "BleConnection",
    "BleConnectionConfig",
    "BleConnectionError",
    "BleError",
    "BleOperationError",
    "BleakClientAdapter",
    "ClientFactory",
    "NotificationHandler",
]
