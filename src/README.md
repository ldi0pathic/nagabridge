# NagaBridge Source Tree

Dieses Verzeichnis enthält den laufenden Code von NagaBridge.

## Struktur (aktuell)

- `nagabridge/core/` – Bus, Adapter-Vertrag, Konfiguration, Health, Logging
- `nagabridge/adapters/` – konkrete Adapter (z. B. `mqtt`) und Platzhalter für Geräteadapter
- `nagabridge/main.py` – minimaler Runtime-Entrypoint

## Before Push (wichtig)

Bitte vor jedem Push die lokalen Qualitätschecks ausführen:

- `docs/development/pre-commit-checklist.md`
- `docs/development/ci-failure-playbook.md`

Kurzversion:

```bash
ruff check src/ tests/
black --target-version py312 --check src/ tests/
PYTHONPATH=src pytest -q tests/test_mock_pipeline.py tests/test_mqtt_adapter.py -k fake_client
```

## MQTT Smoke-Test auf Raspberry Pi

Für den betriebnahen Test (ohne BLE-Hardware) siehe:

- `docs/operations/raspi-smoke-test.md`
