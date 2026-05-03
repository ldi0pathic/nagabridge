from pathlib import Path

from nagabridge.main import build_adapters_from_config


def test_build_adapters_from_config_builds_ble_and_mqtt(tmp_path: Path):
    config = tmp_path / "nagabridge.toml"
    config.write_text(
        """
[system]
log_level = "INFO"

[mqtt]
host = "127.0.0.1"
port = 1883

[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"

[[adapters.ble_device]]
name = "Delta2"
mac = "AA:BB:CC:DD:EE:FE"
type = "delta2"
""",
        encoding="utf-8",
    )

    adapters = build_adapters_from_config(config)
    names = [a.name for a in adapters]
    assert "Powerstream" in names
    assert "Delta2" in names
    assert "mqtt" in names
