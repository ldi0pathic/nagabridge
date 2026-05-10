"""BLE-specific exceptions used by reusable connection helpers."""

from __future__ import annotations


class BleError(RuntimeError):
    """Base class for NagaBridge BLE runtime errors."""


class BleConnectionError(BleError):
    """Raised when a BLE connection cannot be established or restored."""


class BleOperationError(BleError):
    """Raised when an operation requires a connected BLE client."""
