"""Application entrypoint and adapter bootstrapping."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2max.adapter import Delta2MaxAdapter
from nagabridge.adapters.mqtt.adapter import MqttAdapter, MqttAdapterConfig
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig, ConfigError, load_config
from nagabridge.core.logging import configure_logging

if TYPE_CHECKING:
    from nagabridge.core.adapter import Adapter

log = logging.getLogger("nagabridge.main")

DEFAULT_CONFIG_PATH = Path("/opt/nagabridge/nagabridge.toml")

EXIT_SUCCESS = 0
EXIT_CONFIG_ACTION_REQUIRED = 2

DEFAULT_CONFIG_TEMPLATE = """[system]
log_level = "INFO"

# Optional MQTT bridge
# [mqtt]
# host = "192.168.1.10"
# port = 1883

[adapters]
# Add one block per BLE device
# [[adapters.ble_device]]
# name = "Powerstream"
# mac = "AA:BB:CC:DD:EE:FF"
# type = "powerstream"
# serial_number = "POWERSTREAM_SN"
# user_id = "ECOFLOW_USER_ID"
# poll_interval_seconds = 10
# reconnect_attempts = 3
# reconnect_backoff_seconds = 1
# write_with_response = false
"""


def ensure_default_config(path: Path) -> bool:
    """Create a default config file when none exists."""
    if path.exists():
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return True


def _build_ble_adapter(device: BleDeviceConfig) -> Adapter:
    """Create a BLE adapter instance for a configured device."""
    if device.type == "powerstream":
        return PowerstreamAdapter(device)
    if device.type == "delta2":
        return Delta2Adapter(device)
    if device.type == "delta2max":
        return Delta2MaxAdapter(device)
    msg = f"Unsupported device type '{device.type}'"
    raise ValueError(msg)


def build_adapters_from_config(
    config_path: Path = DEFAULT_CONFIG_PATH, *, log_level_override: str | None = None, log_dir: Path | None = None
) -> list[Adapter]:
    """Build all adapters from the TOML configuration file."""
    cfg = load_config(config_path)
    adapters: list[Adapter] = [_build_ble_adapter(device) for device in cfg.devices]

    if cfg.mqtt is not None:
        adapters.append(
            MqttAdapter(
                MqttAdapterConfig(
                    host=cfg.mqtt.host,
                    port=cfg.mqtt.port,
                    user=cfg.mqtt.user,
                    password=cfg.mqtt.password,
                    subscribe_topics=[
                        "ecoflow/powerstream/state",
                        "ecoflow/powerstream/bat_state",
                    ],
                )
            ),
        )

    # Build logger-prefix → file-stem mapping for ADR-012 per-adapter log files.
    # BLE adapters use their device name slug; MQTT gets a fixed name.
    adapter_log_names: dict[str, str] = {}
    for device in cfg.devices:
        slug = device.name.lower().replace(" ", "-")
        # PowerStream adapter logger lives under nagabridge.adapters.powerstream
        prefix = f"nagabridge.adapters.{device.type}"
        adapter_log_names[prefix] = f"ble-{slug}"
    if cfg.mqtt is not None:
        adapter_log_names["nagabridge.adapters.mqtt"] = "mqtt"

    configure_logging(
        log_level_override or cfg.log_level,
        log_dir=log_dir,
        adapter_log_names=adapter_log_names,
    )
    return adapters


async def run(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    log_level_override: str | None = None,
) -> None:
    """Run adapter lifecycle until shutdown signal is received."""
    bus = EventBus()
    adapters = build_adapters_from_config(
        config_path,
        log_level_override=log_level_override,
        log_dir=Path("/var/log/nagabridge"),
    )

    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    log.info("NagaBridge startet - %d Adapter geladen", len(adapters))

    for adapter in adapters:
        await adapter.start(bus)
        log.info("Adapter gestartet: %s", adapter.name)

    await bus.publish("system/nagabridge/status", {"status": "running"})

    log.info("NagaBridge läuft. Warte auf SIGINT/SIGTERM...")
    await shutdown_event.wait()

    log.info("Shutdown eingeleitet...")
    await bus.publish("system/nagabridge/shutdown", {"reason": "signal"})

    for adapter in reversed(adapters):
        await adapter.stop()
        log.info("Adapter gestoppt: %s", adapter.name)

    log.info("NagaBridge beendet.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="nagabridge")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Pfad zur Konfigurationsdatei (Default: /opt/nagabridge/nagabridge.toml)",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Konfiguration prüfen und ohne Start beenden",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Log-Level zur Laufzeit überschreiben",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)

    if ensure_default_config(args.config):
        sys.stderr.write(
            f"Config neu angelegt: {args.config}. Bitte Werte prüfen und erneut starten.\n",
        )
        return EXIT_CONFIG_ACTION_REQUIRED

    try:
        load_config(args.config)
    except (ConfigError, FileNotFoundError) as err:
        sys.stderr.write(f"Config error: {err}\n")
        return EXIT_CONFIG_ACTION_REQUIRED

    if args.check_config:
        sys.stdout.write(f"Config OK: {args.config}\n")
        return EXIT_SUCCESS

    asyncio.run(run(args.config, log_level_override=args.log_level))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
